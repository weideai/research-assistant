import io
import json
import urllib.error
from uuid import uuid4

import pytest

from app import ai_service, db
from app.desktop.bridge import DesktopBridge
from app.models import ApiPreset
from app.services.desktop_workspace import DesktopApplicationService


@pytest.fixture()
def call(app):
    bridge = DesktopBridge(DesktopApplicationService(app), object(), {})

    def invoke(command, **payload):
        return bridge.invoke({"request_id": str(uuid4()), "command": command, "payload": payload})

    return invoke


def test_api_presets_keep_legacy_key_and_switch_active_profile(app, call, monkeypatch):
    legacy_key = "synthetic-key-for-legacy"
    assert call("settings.save", section="api", url="https://legacy.example.test/v1",
                model="legacy-chat", api_key=legacy_key, enabled=True)["ok"]
    legacy = call("settings.get")["data"]["api"]
    created = call("api.presets.save", name="DeepSeek", url="https://api.deepseek.com/chat/completions/",
                   model="example-chat", api_key="synthetic-key-for-deepseek", enabled=True)["data"]
    assert created["url"] == "https://api.deepseek.com"
    assert call("settings.get")["data"]["api"]["id"] == legacy["id"]

    renamed = call("api.presets.save", id=legacy["id"], name="备用接口", url=legacy["url"] + "/models",
                   model=legacy["model"], api_key="", enabled=True)
    assert renamed["ok"] and renamed["data"]["has_key"]
    assert call("api.presets.activate", id=created["id"])["ok"]
    assert call("api.presets.activate", id=created["id"])["ok"]

    settings = call("settings.get")["data"]
    assert settings["api"]["id"] == created["id"]
    assert {preset["name"] for preset in settings["api_presets"]} == {"备用接口", "DeepSeek"}
    with app.app_context():
        original = db.session.get(ApiPreset, legacy["id"])
        assert original.get_api_key() == legacy_key
        assert legacy_key not in original.encrypted_api_key
        assert original.encrypted_api_key not in json.dumps(settings)
        assert ApiPreset.query.filter_by(is_default=True).count() == 1

    def chat_provider(request, timeout):
        assert request.full_url == "https://api.deepseek.com/chat/completions"
        assert request.get_header("Authorization") == "Bearer synthetic-key-for-deepseek"
        payload = json.loads(request.data)
        assert payload["model"] == "example-chat"
        assert "temperature" not in payload
        return io.BytesIO(b'{"choices":[{"message":{"content":"synthetic-reply"}}]}')

    monkeypatch.setattr(ai_service.socket, "getaddrinfo", lambda *a, **kw: [])
    monkeypatch.setattr(ai_service, "_open_url", chat_provider)
    project = call("project.create", title="Synthetic project")["data"]
    proposal = call("ai.propose", target_type="project", target_id=project["id"], prompt="Synthetic request")
    assert proposal["data"]["reply"] == "synthetic-reply"


def test_models_discovery_uses_the_configured_prefix_and_correct_key(call, monkeypatch):
    requests = []

    def provider(request, timeout):
        requests.append((request.get_method(), request.full_url, request.get_header("Authorization")))
        return io.BytesIO(b'{"data":[{"id":"research-chat"},{"id":"research-chat"},{"id":null}]}')

    monkeypatch.setattr(ai_service.socket, "getaddrinfo", lambda *a, **kw: [])
    monkeypatch.setattr(ai_service, "_open_url", provider)
    url = "https://provider.example.test/compatible-mode/v1"
    key = "synthetic-explicit-key"
    first = call("api.models.discover", url=url + "/chat/completions", api_key=key)
    assert first["data"] == {"models": ["research-chat"]}
    assert call("settings.get")["data"]["api_presets"] == []

    preset = call("api.presets.save", name="兼容网关", url=url, model="research-chat", api_key=key)["data"]
    saved = call("api.models.discover", id=preset["id"], url=url + "/models", api_key="")
    assert saved["data"] == first["data"]
    assert requests == [("GET", url + "/models", f"Bearer {key}")] * 2

    other_url = "https://another.example.test/v1"
    assert not call("api.models.discover", id=preset["id"], url=other_url, api_key="")["ok"]
    assert not call("api.presets.save", id=preset["id"], name="错误地址", url=other_url,
                    model="research-chat", api_key="")["ok"]
    assert len(requests) == 2


def test_http_error_is_actionable_without_reflecting_key(call, monkeypatch):
    key = "synthetic-key-reflected-in-server-response"

    def provider(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 401, "Unauthorized", {}, io.BytesIO(key.encode()))

    monkeypatch.setattr(ai_service.socket, "getaddrinfo", lambda *a, **kw: [])
    monkeypatch.setattr(ai_service, "_open_url", provider)
    response = call("api.models.discover", url="https://provider.example.test/v1", api_key=key)
    assert not response["ok"]
    assert "401" in response["error"]["message"]
    assert key not in json.dumps(response)
