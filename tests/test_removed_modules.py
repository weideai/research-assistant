from sqlalchemy import inspect

from app import db


def test_removed_modules_have_no_routes_or_schema_tables(client, auth, app):
    auth.register()

    assert client.get("/papers").status_code == 404
    assert client.get("/statistics").status_code == 404
    assert not any(rule.endpoint == "main.experiment_report_import" for rule in app.url_map.iter_rules())

    with app.app_context():
        inspector = inspect(db.engine)
        assert not inspector.has_table("paper")
        assert not inspector.has_table("reviewer_comment")


def test_assistant_surface_exposes_scope_and_api_controls(client, auth):
    auth.register()
    body = client.get("/dashboard").get_data(as_text=True)

    assert 'id="ai-api-settings"' in body
    assert 'id="ai-context-bar"' in body
    assert 'id="ai-experiment-source-open"' in body
    assert 'id="ai-knowledge-source-open"' in body
    assert 'id="ai-context-page"' in body
    assert 'id="ai-context-label"' not in body
    assert 'id="ai-context-state"' not in body
    assert 'id="ai-input-count"' in body
    assert 'maxlength="20000"' in body
    assert "论文" not in body
