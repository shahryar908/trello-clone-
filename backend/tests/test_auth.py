"""Signup, login, and what happens without a valid token."""


def test_health_needs_no_auth(client):
    # the kubelet calls this one with no credentials — if it ever starts
    # requiring a token, every pod goes CrashLoopBackOff
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_needs_no_auth_and_checks_the_database(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_reports_503_when_the_database_is_gone(client, monkeypatch):
    """Readiness must fail when the dependency fails — that is its whole job.

    503 takes the pod out of the Service's endpoints without restarting it, so
    it rejoins on its own once the database is back.
    """
    from app import database

    class BrokenEngine:
        def connect(self, *args, **kwargs):
            raise OSError("database is unreachable")

    monkeypatch.setattr(database, "engine", BrokenEngine())

    response = client.get("/health/ready")
    assert response.status_code == 503

    # and liveness stays green: the process is fine, so restarting it would
    # only make things worse
    assert client.get("/health").status_code == 200


def test_signup_returns_the_user_without_the_password(client):
    response = client.post(
        "/auth/signup", json={"email": "ada@example.com", "password": "hunter2hunter2"}
    )
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ada@example.com"
    assert "password" not in body, "the bcrypt hash must never leave the server"


def test_duplicate_email_is_rejected(client, make_user):
    make_user("ada@example.com")
    response = client.post(
        "/auth/signup", json={"email": "ada@example.com", "password": "another-one"}
    )
    assert response.status_code == 409


def test_login_returns_a_bearer_token(client, make_user):
    user = make_user("ada@example.com")
    response = client.get("/orgs", headers=user.headers)
    assert response.status_code == 200


def test_wrong_password_and_unknown_email_are_indistinguishable(client, make_user):
    make_user("ada@example.com", password="the-real-password")

    wrong_password = client.post(
        "/auth/login", json={"email": "ada@example.com", "password": "not-it"}
    )
    unknown_email = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "not-it"}
    )

    assert wrong_password.status_code == unknown_email.status_code == 401
    # identical wording on purpose: a different message would tell an attacker
    # which emails are registered
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


def test_protected_route_rejects_missing_and_garbage_tokens(client):
    assert client.get("/orgs").status_code == 401
    assert client.get("/orgs", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401


def test_token_signed_with_a_different_key_is_rejected(client, make_user):
    import jwt

    user = make_user("ada@example.com")
    forged = jwt.encode({"sub": str(user.id)}, "some-other-secret", algorithm="HS256")
    response = client.get("/orgs", headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401
