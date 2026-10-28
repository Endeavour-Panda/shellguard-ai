import pytest

from src.accounts import UserStore


def test_register_then_verify_round_trips(tmp_path):
    store = UserStore(tmp_path / "users.json")
    store.register("alice", "correct-horse")
    assert store.verify("alice", "correct-horse") is True
    assert store.verify("alice", "wrong-password") is False
    assert store.has_any_user() is True


def test_register_rejects_duplicate_username_case_insensitively(tmp_path):
    store = UserStore(tmp_path / "users.json")
    store.register("alice", "correct-horse")
    with pytest.raises(ValueError):
        store.register("Alice", "another-password")


def test_register_rejects_short_password(tmp_path):
    store = UserStore(tmp_path / "users.json")
    with pytest.raises(ValueError):
        store.register("alice", "short")


def test_register_rejects_invalid_username(tmp_path):
    store = UserStore(tmp_path / "users.json")
    with pytest.raises(ValueError):
        store.register("ab", "correct-horse")
    with pytest.raises(ValueError):
        store.register("has space", "correct-horse")


def test_register_rejects_reserved_username(tmp_path):
    store = UserStore(tmp_path / "users.json", reserved_usernames=frozenset({"student"}))
    with pytest.raises(ValueError):
        store.register("student", "correct-horse")


def test_register_enforces_max_users(tmp_path):
    store = UserStore(tmp_path / "users.json", max_users=1)
    store.register("alice", "correct-horse")
    with pytest.raises(ValueError):
        store.register("bob", "correct-horse")


def test_verify_unknown_user_returns_false(tmp_path):
    store = UserStore(tmp_path / "users.json")
    assert store.verify("ghost", "anything") is False


def test_store_persists_across_instances(tmp_path):
    path = tmp_path / "users.json"
    UserStore(path).register("alice", "correct-horse")
    reloaded = UserStore(path)
    assert reloaded.verify("alice", "correct-horse") is True
