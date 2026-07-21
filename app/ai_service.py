from dataclasses import dataclass
import ipaddress
import json
import os
import re
import socket
import urllib.error
import urllib.request
from urllib.parse import urlparse

from flask import current_app, has_app_context


DEFAULT_API_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-5.6-terra"


class AIServiceError(RuntimeError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "API 重定向已被安全策略阻止。", headers, fp)


_opener = urllib.request.build_opener(_NoRedirect)


def _open_url(request, timeout):
    return _opener.open(request, timeout=timeout)


@dataclass(frozen=True)
class AIConfig:
    api_url: str = DEFAULT_API_URL
    api_key: str = ""
    model: str = DEFAULT_MODEL
    enabled: bool = False
    source: str = "environment"
    allow_private: bool = False
    allowed_hosts: tuple = ()


def _env_bool(name, default=False):
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def config_from_environment():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    allow_private = current_app.config["ALLOW_PRIVATE_API_URLS"] if has_app_context() else _env_bool("ALLOW_PRIVATE_API_URLS", True)
    allowed_hosts = current_app.config["AI_ALLOWED_HOSTS"] if has_app_context() else tuple(
        item.strip().lower() for item in os.getenv("AI_ALLOWED_HOSTS", "").split(",") if item.strip()
    )
    return AIConfig(
        api_url=os.getenv("OPENAI_BASE_URL", DEFAULT_API_URL).strip(),
        api_key=api_key,
        model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL,
        enabled=bool(api_key),
        source="environment",
        allow_private=allow_private,
        allowed_hosts=allowed_hosts,
    )


def _host_allowed(hostname, allowed_hosts):
    if not allowed_hosts:
        return True
    hostname = hostname.lower().rstrip(".")
    for allowed in allowed_hosts:
        allowed = allowed.lower().rstrip(".")
        if allowed.startswith("*.") and hostname.endswith(allowed[1:]):
            return True
        if hostname == allowed:
            return True
    return False


def validate_api_url(value, allow_private=False, allowed_hosts=()):
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AIServiceError("API URL 必须是有效的 http:// 或 https:// 地址。")
    if parsed.username or parsed.password:
        raise AIServiceError("API URL 不能包含用户名或密码。")
    if not _host_allowed(parsed.hostname, allowed_hosts):
        raise AIServiceError("该 API 域名不在服务器允许列表中。")
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise AIServiceError("无法解析 API 域名。") from exc
    if not allow_private:
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                raise AIServiceError("生产环境禁止访问本机、内网或保留地址。")
    return value


def _endpoint(config, path):
    api_url = validate_api_url(config.api_url, config.allow_private, config.allowed_hosts)
    if api_url.endswith("/chat/completions"):
        root = api_url.removesuffix("/chat/completions")
        return api_url if path == "chat/completions" else f"{root}/{path}"
    if api_url.endswith("/models"):
        root = api_url.removesuffix("/models")
        return api_url if path == "models" else f"{root}/{path}"
    return f"{api_url}/{path}"


def _headers(api_key):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _read_json(request, timeout):
    try:
        with _open_url(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read().decode("utf-8")[:500]
        except Exception:
            detail = ""
        message = f"API 返回 HTTP {exc.code}"
        if detail:
            message += f"：{detail}"
        raise AIServiceError(message) from exc
    except urllib.error.URLError as exc:
        raise AIServiceError(f"无法连接 API：{exc.reason}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AIServiceError("API 返回内容不是有效 JSON。") from exc


def list_models(config):
    request = urllib.request.Request(_endpoint(config, "models"), headers=_headers(config.api_key), method="GET")
    body = _read_json(request, timeout=20)
    data = body.get("data", []) if isinstance(body, dict) else []
    models = sorted({str(item.get("id", "")).strip() for item in data if isinstance(item, dict) and item.get("id")})
    if not models:
        raise AIServiceError("连接成功，但 /models 没有返回可用模型。你仍可手动填写模型名称。")
    return models


def organize_note(note, config=None):
    config = config or config_from_environment()
    if not config.enabled:
        return local_draft(note), "local"
    model = config.model.strip()
    if not model:
        raise AIServiceError("请先配置模型名称。")
    schema = '{"title":"", "objective":"", "conditions":"", "content":"", "result":"待确认", "remark":""}'
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": f"你是医学科研记录助手。只输出合法 JSON，不得编造原始笔记中没有的数据。格式：{schema}"},
            {"role": "user", "content": note},
        ],
    }
    if model.startswith("gpt-5.6"):
        payload["reasoning_effort"] = "none"
    request = urllib.request.Request(
        _endpoint(config, "chat/completions"),
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=_headers(config.api_key),
        method="POST",
    )
    body = _read_json(request, timeout=45)
    try:
        content = body["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            raise AIServiceError("AI 返回内容不是可识别的 JSON。")
        result = json.loads(match.group())
        return {key: str(result.get(key, "")) for key in json.loads(schema)}, "api"
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise AIServiceError("AI 返回结构不符合 Chat Completions 格式。") from exc


def local_draft(note):
    lines = [line.strip(" -•\t") for line in note.splitlines() if line.strip()]
    title = lines[0][:80] if lines else "未命名实验记录"
    lower_note = note.lower()
    if any(word in lower_note for word in ("失败", "污染", "异常", "fail")):
        result = "失败"
    elif any(word in lower_note for word in ("成功", "正常", "完成", "success")):
        result = "成功"
    else:
        result = "待确认"
    return {"title": title, "objective": "", "conditions": "", "content": note.strip(), "result": result,
            "remark": "本地规则生成的草稿，请核对并补充实验条件与结论。"}
