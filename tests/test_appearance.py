import base64
import io

from app import db
from app.models import AppearanceSetting, User


ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def test_theme_and_color_mode_are_saved_per_user(client, auth, app):
    auth.register()
    response = client.post("/settings/appearance", data={
        "theme": "tech", "dark_mode": "1", "next": "/tasks", "action": "save",
    })
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/tasks")

    with app.app_context():
        setting = AppearanceSetting.query.one()
        assert setting.theme == "tech"
        assert setting.color_mode == "dark"

    page = client.get("/")
    assert b'data-theme="tech"' in page.data
    assert b'data-mode="dark"' in page.data


def test_background_upload_is_private_and_can_be_cleared(client, auth, app):
    auth.register(email="background-owner@example.com")
    response = client.post("/settings/appearance", data={
        "theme": "cute",
        "action": "save",
        "next": "/",
        "background": (io.BytesIO(ONE_PIXEL_PNG), "background.png"),
    }, content_type="multipart/form-data", follow_redirects=True)
    assert response.status_code == 200
    assert b"has-custom-background" in response.data

    background = client.get("/settings/appearance/background")
    assert background.status_code == 200
    assert background.mimetype == "image/png"
    assert background.data == ONE_PIXEL_PNG

    auth.logout()
    auth.register(email="other-background@example.com")
    assert client.get("/settings/appearance/background").status_code == 404

    auth.logout()
    auth.login(email="background-owner@example.com")
    response = client.post("/settings/appearance", data={
        "action": "clear_background", "next": "/",
    }, follow_redirects=True)
    assert b"has-custom-background" not in response.data
    assert client.get("/settings/appearance/background").status_code == 404


def test_invalid_background_is_rejected(client, auth, app):
    auth.register()
    response = client.post("/settings/appearance", data={
        "theme": "minimal",
        "action": "save",
        "next": "/",
        "background": (io.BytesIO(b"<html>not an image</html>"), "background.png"),
    }, content_type="multipart/form-data", follow_redirects=True)
    assert "只支持 PNG、JPEG 或 WebP".encode() in response.data
    with app.app_context():
        assert AppearanceSetting.query.count() == 0


def test_viewer_can_change_personal_appearance(client, auth, app):
    auth.register()
    with app.app_context():
        user = User.query.filter_by(email="researcher@example.com").one()
        user.role = "viewer"
        user.session_version += 1
        db.session.commit()
    auth.login()

    response = client.post("/settings/appearance", data={
        "theme": "minimal", "dark_mode": "1", "action": "save", "next": "/",
    })
    assert response.status_code == 302
    with app.app_context():
        setting = AppearanceSetting.query.one()
        assert (setting.theme, setting.color_mode) == ("minimal", "dark")
