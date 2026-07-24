from dataclasses import dataclass
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.request
from urllib.parse import urlparse

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
    source: str = "explicit"
    allow_private: bool = False
    allowed_hosts: tuple = ()

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


MODEL_CAPABILITIES = ("vision", "reasoning", "web_search", "tools")
MODEL_CAPABILITY_STATUSES = {"declared", "inferred", "unknown"}


def _normalized_capability_label(value):
    value = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(value or "").strip())
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _capability_from_label(value):
    label = _normalized_capability_label(value)
    for prefix in ("supports_", "support_", "has_"):
        if label.startswith(prefix):
            label = label[len(prefix):]
            break
    aliases = {
        "vision": {
            "vision", "image_input", "image_inputs", "input_image", "input_images",
            "multimodal", "multi_modal",
        },
        "reasoning": {
            "reasoning", "reasoning_effort", "include_reasoning", "reasoner", "thinking", "extended_thinking",
        },
        "web_search": {
            "web_search", "web_search_preview", "internet_search", "browser_search",
            "search_tool",
        },
        "tools": {
            "tools", "tool", "tool_use", "tool_call", "tool_calls", "tool_calling",
            "tool_choice", "parallel_tool_calls", "functions", "function_call", "function_calls",
            "function_calling",
        },
    }
    return next((name for name, values in aliases.items() if label in values), None)


def _declared_support(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "supported", "enabled", "available"}:
            return True
        if normalized in {"false", "no", "unsupported", "disabled", "unavailable"}:
            return False
    if isinstance(value, dict):
        for key in ("supported", "enabled", "available"):
            if key in value:
                return _declared_support(value[key])
    return None


def _declared_model_capabilities(item):
    declared = {}

    def add(label, value=True):
        capability = _capability_from_label(label)
        supported = _declared_support(value)
        if capability and supported is not None and capability not in declared:
            declared[capability] = supported

    containers = [item]
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        containers.append(metadata)

    for container in containers:
        for key, value in container.items():
            add(key, value)
        for field in ("capabilities", "features"):
            values = container.get(field)
            if isinstance(values, dict):
                for key, value in values.items():
                    add(key, value)
            elif isinstance(values, (list, tuple, set)):
                for value in values:
                    add(value)
        for field in ("supported_features", "supported_parameters"):
            values = container.get(field)
            if isinstance(values, (list, tuple, set)):
                for value in values:
                    add(value)

    modality_containers = list(containers)
    for container in containers:
        architecture = next((
            value for key, value in container.items()
            if _normalized_capability_label(key) == "architecture"
        ), None)
        if isinstance(architecture, dict):
            modality_containers.append(architecture)
    if "vision" not in declared:
        for container in modality_containers:
            modalities = next((
                value for key, value in container.items()
                if _normalized_capability_label(key) == "input_modalities"
            ), None)
            if not isinstance(modalities, (list, tuple, set)) or not modalities:
                continue
            normalized = {_normalized_capability_label(value) for value in modalities}
            declared["vision"] = bool(normalized & {"image", "images", "image_url", "input_image"})
            break
    return declared


def _model_name_inferences(model_id, official_openai=False):
    name = model_id.strip().lower()
    inferred = set()
    vision_family = re.match(
        r"^(?:gpt-(?:4o|4\.1|5)(?:[-.]|$)|o(?:3|4)(?:[-.]|$)|"
        r"claude-(?:3|4)(?:[-.]|$)|gemini-(?:1\.5|2|2\.5|3)(?:[-.]|$))",
        name,
    )
    if vision_family or re.search(r"(?:^|[-_/])(?:vision|vl|llava|pixtral)(?:[-_/]|$)", name):
        inferred.add("vision")

    reasoning_family = re.match(r"^(?:gpt-5(?:[-.]|$)|o(?:1|3|4)(?:[-.]|$))", name)
    if reasoning_family or re.search(
        r"(?:^|[-_/])(?:reasoning|reasoner|thinking|qwq)(?:[-_/]|$)|(?:^|[-_/])deepseek[-_/]?r1(?:[-_/]|$)",
        name,
    ):
        inferred.add("reasoning")

    tool_family = re.match(
        r"^(?:gpt-(?:4o|4\.1|5)(?:[-.]|$)|claude-(?:3|4)(?:[-.]|$)|"
        r"gemini-(?:1\.5|2|2\.5|3)(?:[-.]|$))",
        name,
    )
    if tool_family:
        inferred.add("tools")

    if official_openai and re.match(r"^(?:gpt-(?:4o|4\.1|5)(?:[-.]|$)|o(?:3|4)(?:[-.]|$))", name):
        inferred.add("web_search")
    return inferred


def describe_model(model_id, raw=None, api_url=""):
    """Return normalized capability evidence for one saved or discovered model."""
    item = raw if isinstance(raw, dict) else {}
    model_id = str(model_id or item.get("id", "")).strip()
    declared = _declared_model_capabilities(item)
    official_openai = (urlparse(api_url).hostname or "").lower() == "api.openai.com"
    inferred = _model_name_inferences(model_id, official_openai=official_openai)
    capabilities = {}
    for capability in MODEL_CAPABILITIES:
        if capability in declared:
            capabilities[capability] = {"supported": declared[capability], "status": "declared"}
        elif capability == "web_search" and not official_openai:
            capabilities[capability] = {"supported": None, "status": "unknown"}
        elif capability in inferred:
            capabilities[capability] = {"supported": True, "status": "inferred"}
        else:
            capabilities[capability] = {"supported": None, "status": "unknown"}
    return {
        "id": model_id,
        "owned_by": str(item.get("owned_by") or item.get("owner") or "").strip(),
        "capabilities": capabilities,
    }


def model_capability_snapshot(model_id, descriptor=None, api_url=""):
    """Return a validated, provider-bound snapshot suitable for persistence."""
    model_id = str(model_id or "").strip()
    normalized_api_url = str(api_url or "").strip().rstrip("/")
    fallback = describe_model(model_id, api_url=normalized_api_url)
    candidate = descriptor if isinstance(descriptor, dict) else {}
    candidate_model_id = str(candidate.get("model_id") or candidate.get("id") or "").strip()
    candidate_api_url = str(candidate.get("api_url") or "").strip().rstrip("/")
    candidate_capabilities = candidate.get("capabilities")
    use_candidate = (
        bool(model_id)
        and candidate_model_id == model_id
        and candidate_api_url == normalized_api_url
        and isinstance(candidate_capabilities, dict)
    )

    capabilities = {}
    for name in MODEL_CAPABILITIES:
        evidence = candidate_capabilities.get(name) if use_candidate else None
        if not isinstance(evidence, dict):
            capabilities[name] = fallback["capabilities"][name]
            continue
        status = str(evidence.get("status") or "").strip().lower()
        supported = evidence.get("supported")
        if status not in MODEL_CAPABILITY_STATUSES or not (
                supported is None or isinstance(supported, bool)):
            capabilities[name] = fallback["capabilities"][name]
        elif status == "unknown" or supported is None or (status == "inferred" and supported is False):
            capabilities[name] = {"supported": None, "status": "unknown"}
        else:
            capabilities[name] = {"supported": supported, "status": status}

    return {
        "model_id": model_id,
        "api_url": normalized_api_url,
        "capabilities": capabilities,
    }


def describe_model_from_snapshot(model_id, snapshot=None, api_url=""):
    """Build a display descriptor from persisted capability evidence."""
    if isinstance(snapshot, str):
        try:
            snapshot = json.loads(snapshot)
        except (TypeError, json.JSONDecodeError):
            snapshot = None
    normalized = model_capability_snapshot(model_id, snapshot, api_url=api_url)
    return {
        "id": normalized["model_id"],
        "owned_by": "",
        "capabilities": normalized["capabilities"],
    }


def discover_models(config):
    """Fetch and normalize the provider's model directory."""
    request = urllib.request.Request(_endpoint(config, "models"), headers=_headers(config.api_key), method="GET")
    body = _read_json(request, timeout=20)
    if isinstance(body, list):
        data = body
    elif isinstance(body, dict):
        data = body.get("data")
        if isinstance(data, dict):
            data = data.get("data") or data.get("models")
        if not isinstance(data, list):
            data = body.get("models")
        if isinstance(data, dict):
            data = data.get("data") or data.get("models")
        if not isinstance(data, list):
            data = []
    else:
        data = []
    models = {}
    for item in data:
        if isinstance(item, str):
            item = {"id": item}
        if not isinstance(item, dict):
            continue
        model_id = next((
            str(item.get(key, "")).strip() for key in ("id", "name", "model")
            if str(item.get(key, "")).strip()
        ), "")
        if not model_id:
            continue
        entry = describe_model(model_id, raw=item, api_url=config.api_url)
        models.setdefault(entry["id"], entry)
    if not models:
        raise AIServiceError("连接成功，但 /models 没有返回可用模型。你仍可手动填写模型名称。")
    return [models[model_id] for model_id in sorted(models)]


def list_models(config):
    """Return model IDs using the legacy list-based contract."""
    return [item["id"] for item in discover_models(config)]


def organize_note(note, config=None):
    config = config or AIConfig(api_url="", model="", enabled=False, source="none")
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


def _is_official_openai(config):
    return (urlparse(config.api_url).hostname or "").lower() == "api.openai.com"


def _assistant_result(content):
    text = str(content or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S | re.I)
    candidate = fenced.group(1) if fenced else text
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, re.S)
        try:
            parsed = json.loads(match.group()) if match else None
        except json.JSONDecodeError:
            parsed = None
    if not isinstance(parsed, dict):
        return {"reply": text, "proposal": None}
    reply = str(parsed.get("reply") or parsed.get("answer") or "").strip()
    proposal = parsed.get("proposal") if isinstance(parsed.get("proposal"), dict) else None
    return {"reply": reply or "已完成分析，请核对下方建议。", "proposal": proposal}


def _responses_content(body):
    texts = []
    references = []
    for item in body.get("output", []) if isinstance(body, dict) else []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content", []):
            if not isinstance(part, dict) or part.get("type") != "output_text":
                continue
            texts.append(str(part.get("text", "")))
            for annotation in part.get("annotations", []):
                if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
                    continue
                citation = annotation.get("url_citation") if isinstance(annotation.get("url_citation"), dict) else annotation
                url = str(citation.get("url", "")).strip()
                if url:
                    references.append({"title": str(citation.get("title") or url), "url": url})
    unique = []
    seen = set()
    for reference in references:
        if reference["url"] not in seen:
            unique.append(reference)
            seen.add(reference["url"])
    return "\n".join(texts).strip(), unique


def chat_with_assistant(messages, system_prompt, config=None, web_access=False):
    config = config or AIConfig(api_url="", model="", enabled=False, source="none")
    if not config.enabled:
        raise AIServiceError("请先在 API 设置中启用 API 并配置 Key。")
    if not config.model.strip():
        raise AIServiceError("请先配置模型名称。")

    normalized = [
        {"role": item.get("role", "user"), "content": str(item.get("content", ""))}
        for item in messages if item.get("role") in {"user", "assistant"}
    ]
    references = []
    web_used = False
    if web_access and _is_official_openai(config):
        payload = {
            "model": config.model,
            "input": [{"role": "system", "content": system_prompt}, *normalized],
            "tools": [{"type": "web_search"}],
        }
        request = urllib.request.Request(
            _endpoint(config, "responses"),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=_headers(config.api_key), method="POST",
        )
        body = _read_json(request, timeout=90)
        content, references = _responses_content(body)
        if not content:
            raise AIServiceError("Responses API 没有返回可读取的文本内容。")
        web_used = True
    else:
        compatibility_note = (
            "当前是兼容 API，未启用内置网页检索。不得声称已联网或编造引用。"
            if web_access else ""
        )
        payload = {
            "model": config.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": f"{system_prompt}\n{compatibility_note}".strip()},
                *normalized,
            ],
        }
        request = urllib.request.Request(
            _endpoint(config, "chat/completions"),
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=_headers(config.api_key), method="POST",
        )
        body = _read_json(request, timeout=90)
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIServiceError("AI 返回结构不符合 Chat Completions 格式。") from exc
        for citation in body.get("citations", []) if isinstance(body, dict) else []:
            if isinstance(citation, str) and citation.startswith(("http://", "https://")):
                references.append({"title": citation, "url": citation})
            elif isinstance(citation, dict) and citation.get("url"):
                references.append({"title": str(citation.get("title") or citation["url"]), "url": str(citation["url"])})

    result = _assistant_result(content)
    result["references"] = references
    result["web_used"] = web_used
    result["web_requested"] = bool(web_access)
    return result


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
