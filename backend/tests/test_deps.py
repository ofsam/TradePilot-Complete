from app.deps import bearer_token, is_auth_required


def test_bearer_token_parses():
    assert bearer_token(None) == ""
    assert bearer_token("Bearer abc") == "abc"
    assert bearer_token("bearer xyz") == "xyz"


def test_auth_required_default(monkeypatch):
    monkeypatch.delenv("REQUIRE_AUTH", raising=False)
    assert is_auth_required() is True
    monkeypatch.setenv("REQUIRE_AUTH", "false")
    assert is_auth_required() is False
