import json

import pytest

from app.ai_service import AIConfig, AIServiceError, chat_with_assistant, list_models, organize_note, validate_api_url


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.body, ensure_ascii=False).encode("utf-8")


def test_gpt_56_request_preserves_low_latency_reasoning(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return FakeResponse({"choices": [{"message": {"content": json.dumps({
            "title": "WB 记录", "objective": "", "conditions": "5 μM",
            "content": "完成 WB。", "result": "成功", "remark": ""
        }, ensure_ascii=False)}}]})

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5.6-terra")
    monkeypatch.setattr("app.ai_service._open_url", fake_urlopen)
    result, mode = organize_note("完成 WB。")

    assert mode == "api"
    assert result["result"] == "成功"
    assert captured["url"].endswith("/chat/completions")
    assert captured["payload"]["reasoning_effort"] == "none"
    assert captured["timeout"] == 45


def test_compatible_provider_does_not_receive_openai_specific_reasoning(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured.update(json.loads(request.data.decode("utf-8")))
        return FakeResponse({"choices": [{"message": {"content":
            '{"title":"记录","objective":"","conditions":"","content":"完成。","result":"待确认","remark":""}'
        }}]})

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "compatible-model")
    monkeypatch.setattr("app.ai_service._open_url", fake_urlopen)
    organize_note("完成。")

    assert "reasoning_effort" not in captured


def test_full_chat_completions_url_is_used_without_duplicate_path(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse({"choices": [{"message": {"content":
            '{"title":"记录","objective":"","conditions":"","content":"完成。","result":"待确认","remark":""}'
        }}]})

    monkeypatch.setattr("app.ai_service._open_url", fake_urlopen)
    config = AIConfig(api_url="http://127.0.0.1:1234/v1/chat/completions", model="local-model", enabled=True,
                      allow_private=True)
    organize_note("完成。", config)

    assert captured["url"] == "http://127.0.0.1:1234/v1/chat/completions"


def test_model_listing_uses_models_endpoint_and_allows_no_key(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["authorization"] = request.headers.get("Authorization")
        return FakeResponse({"data": [{"id": "model-b"}, {"id": "model-a"}]})

    monkeypatch.setattr("app.ai_service._open_url", fake_urlopen)
    models = list_models(AIConfig(api_url="http://127.0.0.1:1234/v1", model="model-a", enabled=True,
                                 allow_private=True))

    assert models == ["model-a", "model-b"]
    assert captured["url"] == "http://127.0.0.1:1234/v1/models"
    assert captured["authorization"] is None


def test_private_and_unapproved_api_hosts_are_blocked(monkeypatch):
    with pytest.raises(AIServiceError, match="内网"):
        validate_api_url("http://127.0.0.1:1234/v1")

    monkeypatch.setattr("socket.getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))])
    assert validate_api_url("https://api.example.com/v1", allowed_hosts=("*.example.com",)) == "https://api.example.com/v1"
    with pytest.raises(AIServiceError, match="允许列表"):
        validate_api_url("https://other.example.net/v1", allowed_hosts=("api.example.com",))


def test_official_web_chat_uses_responses_and_returns_real_citations(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({
            "output": [{
                "type": "message",
                "content": [{
                    "type": "output_text",
                    "text": '{"reply":"Evidence summary","proposal":null}',
                    "annotations": [{"type": "url_citation", "url": "https://example.org/paper", "title": "Paper"}],
                }],
            }],
        })

    monkeypatch.setattr("socket.getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("104.18.7.192", 443))])
    monkeypatch.setattr("app.ai_service._open_url", fake_urlopen)
    result = chat_with_assistant(
        [{"role": "user", "content": "Find evidence"}], "Return JSON",
        AIConfig(api_url="https://api.openai.com/v1", api_key="test", model="test-model", enabled=True),
        web_access=True,
    )

    assert captured["url"].endswith("/responses")
    assert captured["payload"]["tools"] == [{"type": "web_search"}]
    assert result["reply"] == "Evidence summary"
    assert result["references"] == [{"title": "Paper", "url": "https://example.org/paper"}]
    assert result["web_used"] is True
