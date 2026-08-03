from app import db
from app.models import AppearanceSetting, User


def test_application_shell_has_no_appearance_controls(client, auth):
    auth.register()

    page = client.get("/")

    assert page.status_code == 200
    for retired_hook in (
        b"appearance-toggle",
        b"appearance-dialog",
        b"data-theme",
        b"data-mode",
        b"has-custom-background",
        b"themes.css",
    ):
        assert retired_hook not in page.data


def test_retired_appearance_routes_return_not_found(client, auth):
    auth.register()

    assert client.post("/settings/appearance").status_code == 404
    assert client.get("/settings/appearance/background").status_code == 404


def test_legacy_appearance_rows_do_not_change_the_fixed_interface(client, auth, app):
    auth.register()
    with app.app_context():
        user = User.query.filter_by(email="researcher@example.com").one()
        db.session.add(AppearanceSetting(
            user_id=user.id,
            theme="cute",
            color_mode="dark",
            background_filename="legacy-background.png",
        ))
        db.session.commit()

    page = client.get("/")

    assert page.status_code == 200
    assert b"data-theme" not in page.data
    assert b"data-mode" not in page.data
    assert b"has-custom-background" not in page.data
