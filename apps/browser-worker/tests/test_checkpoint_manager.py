"""Pure unit tests for CheckpointManager's redaction logic - no browser, no DB, fast.

Covers the exact bug found and fixed in this session: form_state (a raw DOM
scrape) was reaching Postgres completely unredacted because redaction was
only ever applied to filled_fields.
"""
from browser_worker.services.checkpoint_manager import CheckpointManager


def test_redacts_password_fields():
    cm = CheckpointManager()
    result = cm._redact_sensitive({"password": "hunter2", "email": "a@b.com"})
    assert result["password"] == "[REDACTED]"
    assert result["email"] == "a@b.com"


def test_redacts_all_known_sensitive_keys():
    cm = CheckpointManager()
    raw = {
        "password": "x",
        "ssn": "123-45-6789",
        "social_security": "y",
        "credit_card": "4111111111111111",
        "cvv": "123",
        "pin": "0000",
        "first_name": "Not Sensitive",
    }
    result = cm._redact_sensitive(raw)
    for key in ("password", "ssn", "social_security", "credit_card", "cvv", "pin"):
        assert result[key] == "[REDACTED]", f"{key} should have been redacted"
    assert result["first_name"] == "Not Sensitive"


def test_redaction_is_case_insensitive_on_key_substring():
    cm = CheckpointManager()
    result = cm._redact_sensitive({"user_password_confirm": "x", "confirm_pin_code": "y"})
    assert result["user_password_confirm"] == "[REDACTED]"
    assert result["confirm_pin_code"] == "[REDACTED]"


def test_nested_form_state_dicts_each_get_redacted():
    """form_state is {"form_0": {field: value, ...}} - the actual shape
    CheckpointManager.create_checkpoint redacts before either write path."""
    cm = CheckpointManager()
    form_state = {
        "form_0": {"email": "a@b.com", "password": "hunter2"},
        "form_1": {"ssn": "123-45-6789", "city": "Springfield"},
    }
    redacted = {form_key: cm._redact_sensitive(fields) for form_key, fields in form_state.items()}
    assert redacted["form_0"]["password"] == "[REDACTED]"
    assert redacted["form_0"]["email"] == "a@b.com"
    assert redacted["form_1"]["ssn"] == "[REDACTED]"
    assert redacted["form_1"]["city"] == "Springfield"


def test_local_fallback_mode_when_no_db_supplied():
    """No db/browser_session_id -> _durable must be False, matching the
    standalone host demo path (run_demo.sh), which has no database access."""
    cm = CheckpointManager()
    assert cm._durable is False


def test_durable_mode_when_db_and_session_supplied():
    cm = CheckpointManager(db=object(), browser_session_id="11111111-1111-1111-1111-111111111111")
    assert cm._durable is True
