import json

import pytest

from app.ai_service import (
    AIConfig, AIServiceError, chat_with_assistant, describe_model, describe_model_from_snapshot,
    discover_models, list_models, model_capability_snapshot, organize_note, validate_api_url,
)


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

    monkeypatch.setattr("app.ai_service._open_url", fake_urlopen)
    result, mode = organize_note("完成 WB。", AIConfig(
        api_url="https://api.openai.com/v1", api_key="test-key",
        model="gpt-5.6-terra", enabled=True, allow_private=True,
    ))

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

    monkeypatch.setattr("app.ai_service._open_url", fake_urlopen)
    organize_note("完成。", AIConfig(
        api_url="https://provider.example.test/v1", api_key="test-key",
        model="compatible-model", enabled=True, allow_private=True,
    ))

    assert "reasoning_effort" not in captured


def test_environment_variables_do_not_enable_ai_without_an_account_preset(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-used")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.example.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "environment-model")

    result, mode = organize_note("完成 WB。")

    assert mode == "local"
    assert result["content"] == "完成 WB。"
    with pytest.raises(AIServiceError, match="API 设置"):
        chat_with_assistant([{"role": "user", "content": "测试"}], "测试")


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


@pytest.mark.parametrize("body, expected", [
    ({"models": ["model-a", {"name": "model-b", "owner": "local-lab"}]}, ["model-a", "model-b"]),
    ([{"model": "model-c"}, "model-d"], ["model-c", "model-d"]),
    ({"data": {"models": [{"id": "model-e"}]}}, ["model-e"]),
])
def test_model_discovery_accepts_common_compatible_response_shapes(monkeypatch, body, expected):
    def fake_urlopen(_request, timeout):
        return FakeResponse(body)

    monkeypatch.setattr("app.ai_service._open_url", fake_urlopen)
    models = discover_models(AIConfig(
        api_url="http://127.0.0.1:1234/v1", enabled=True, allow_private=True,
    ))

    assert [item["id"] for item in models] == expected
    if expected == ["model-a", "model-b"]:
        assert models[1]["owned_by"] == "local-lab"


def test_model_discovery_parses_camel_case_capability_metadata():
    model = describe_model("provider-model", raw={
        "supportsFunctionCalling": True,
        "architecture": {"inputModalities": ["text", "image"]},
    })

    assert model["capabilities"]["tools"] == {"supported": True, "status": "declared"}
    assert model["capabilities"]["vision"] == {"supported": True, "status": "declared"}


def test_model_discovery_parses_declared_metadata_including_web_search(monkeypatch):
    def fake_urlopen(_request, timeout):
        return FakeResponse({"data": [
            {
                "id": "metadata-model",
                "owned_by": "research-provider",
                "capabilities": {
                    "vision": True,
                    "reasoning": {"supported": False},
                    "web_search": True,
                },
                "supported_parameters": ["tools"],
            },
            {
                "id": "text-only-model",
                "architecture": {"input_modalities": ["text"]},
            },
        ]})

    monkeypatch.setattr("app.ai_service._open_url", fake_urlopen)
    models = discover_models(AIConfig(
        api_url="http://127.0.0.1:1234/v1", enabled=True, allow_private=True,
    ))

    metadata = models[0]
    assert metadata["id"] == "metadata-model"
    assert metadata["owned_by"] == "research-provider"
    assert metadata["capabilities"]["vision"] == {"supported": True, "status": "declared"}
    assert metadata["capabilities"]["reasoning"] == {"supported": False, "status": "declared"}
    assert metadata["capabilities"]["tools"] == {"supported": True, "status": "declared"}
    assert metadata["capabilities"]["web_search"] == {"supported": True, "status": "declared"}
    assert models[1]["capabilities"]["vision"] == {"supported": False, "status": "declared"}


def test_model_discovery_uses_conservative_name_inference(monkeypatch):
    def fake_urlopen(_request, timeout):
        return FakeResponse({"data": [
            {"id": "deepseek-r1"},
            {"id": "gpt-5.6-terra"},
            {"id": "revision-model"},
        ]})

    monkeypatch.setattr("app.ai_service._open_url", fake_urlopen)
    models = {
        item["id"]: item for item in discover_models(AIConfig(
            api_url="http://127.0.0.1:1234/v1", enabled=True, allow_private=True,
        ))
    }

    assert models["deepseek-r1"]["capabilities"]["reasoning"] == {
        "supported": True, "status": "inferred",
    }
    assert models["gpt-5.6-terra"]["capabilities"]["vision"] == {
        "supported": True, "status": "inferred",
    }
    assert models["gpt-5.6-terra"]["capabilities"]["tools"] == {
        "supported": True, "status": "inferred",
    }
    assert models["gpt-5.6-terra"]["capabilities"]["web_search"] == {
        "supported": None, "status": "unknown",
    }
    assert all(
        capability == {"supported": None, "status": "unknown"}
        for capability in models["revision-model"]["capabilities"].values()
    )


def test_official_provider_can_infer_or_declare_web_search(monkeypatch):
    monkeypatch.setattr("socket.getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("104.18.7.192", 443))])

    def fake_urlopen(_request, timeout):
        return FakeResponse({"data": [
            {"id": "gpt-5.6-terra"},
            {"id": "custom-model", "features": {"web_search": True}},
        ]})

    monkeypatch.setattr("app.ai_service._open_url", fake_urlopen)
    models = {
        item["id"]: item for item in discover_models(AIConfig(
            api_url="https://api.openai.com/v1", api_key="test", enabled=True,
        ))
    }

    assert models["gpt-5.6-terra"]["capabilities"]["web_search"] == {
        "supported": True, "status": "inferred",
    }
    assert models["custom-model"]["capabilities"]["web_search"] == {
        "supported": True, "status": "declared",
    }


def test_describe_model_matches_discovery_contract_without_raw_metadata():
    model = describe_model("gpt-5.6-terra", api_url="https://api.openai.com/v1")

    assert model["id"] == "gpt-5.6-terra"
    assert model["owned_by"] == ""
    assert model["capabilities"]["reasoning"] == {"supported": True, "status": "inferred"}
    assert model["capabilities"]["web_search"] == {"supported": True, "status": "inferred"}
    assert set(model["capabilities"]) == {"vision", "reasoning", "web_search", "tools"}


def test_model_capability_snapshot_preserves_evidence_and_rejects_stale_provider():
    descriptor = {
        "model_id": "gpt-5.6-terra",
        "api_url": "http://provider.example/v1/",
        "capabilities": {
            "vision": {"supported": False, "status": "declared"},
            "reasoning": {"supported": True, "status": "declared"},
            "web_search": {"supported": None, "status": "unknown"},
            "tools": {"supported": False, "status": "declared"},
        },
    }
    snapshot = model_capability_snapshot(
        "gpt-5.6-terra", descriptor, api_url="http://provider.example/v1"
    )
    restored = describe_model_from_snapshot(
        "gpt-5.6-terra", json.dumps(snapshot), api_url="http://provider.example/v1"
    )

    assert snapshot["api_url"] == "http://provider.example/v1"
    assert restored["capabilities"]["vision"] == {"supported": False, "status": "declared"}
    assert restored["capabilities"]["tools"] == {"supported": False, "status": "declared"}

    stale = describe_model_from_snapshot(
        "gpt-5.6-terra", json.dumps(snapshot), api_url="http://different.example/v1"
    )
    assert stale["capabilities"]["vision"] == {"supported": True, "status": "inferred"}


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
