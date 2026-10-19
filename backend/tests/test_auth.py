"""认证接口测试：注册、重复注册、登录成功/失败、未登录访问保护。"""
from tests.conftest import auth_header, register


class TestRegister:
    def test_register_success(self, client):
        r = client.post("/api/auth/register", json={"username": "alice", "password": "secret123"})
        assert r.status_code == 201
        assert r.json()["access_token"]
        assert r.json()["username"] == "alice"

    def test_duplicate_username_conflict(self, client):
        register(client, "alice")
        r = client.post("/api/auth/register", json={"username": "alice", "password": "other123"})
        assert r.status_code == 409

    def test_short_password_rejected(self, client):
        r = client.post("/api/auth/register", json={"username": "bob", "password": "123"})
        assert r.status_code == 422


class TestLogin:
    def test_login_success(self, client):
        register(client, "alice", "secret123")
        r = client.post("/api/auth/login", json={"username": "alice", "password": "secret123"})
        assert r.status_code == 200
        assert r.json()["access_token"]

    def test_login_wrong_password(self, client):
        register(client, "alice", "secret123")
        r = client.post("/api/auth/login", json={"username": "alice", "password": "wrongpass"})
        assert r.status_code == 401

    def test_login_unknown_user(self, client):
        r = client.post("/api/auth/login", json={"username": "nobody", "password": "whatever1"})
        assert r.status_code == 401


class TestAuthProtection:
    def test_survey_list_requires_login(self, client):
        r = client.get("/api/surveys")
        assert r.status_code == 401

    def test_survey_list_with_token(self, client):
        token = register(client)
        r = client.get("/api/surveys", headers=auth_header(token))
        assert r.status_code == 200
        assert r.json() == []
