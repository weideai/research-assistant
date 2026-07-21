import pytest

from app import create_app, db


@pytest.fixture()
def app():
    app = create_app({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SECRET_KEY": "test-key",
        "CREDENTIAL_ENCRYPTION_KEY": "test-credential-key",
        "RATELIMIT_ENABLED": False,
        "ALLOW_PUBLIC_REGISTRATION": True,
        "BOOTSTRAP_FIRST_USER_ADMIN": True,
        "EXPOSE_DEV_EMAIL_LINKS": True,
        "ALLOW_PRIVATE_API_URLS": True,
        "AI_SETTINGS_ADMIN_ONLY": False,
    })
    with app.app_context():
        db.create_all()
    yield app
    with app.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def auth(client):
    class AuthActions:
        def register(self, email="researcher@example.com", password="Password1234", name="研究员"):
            return client.post("/register", data={"name": name, "email": email, "password": password}, follow_redirects=True)

        def login(self, email="researcher@example.com", password="Password1234"):
            return client.post("/login", data={"email": email, "password": password}, follow_redirects=True)

        def logout(self):
            return client.post("/logout", follow_redirects=True)

    return AuthActions()
