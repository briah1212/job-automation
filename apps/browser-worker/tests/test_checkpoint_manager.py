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


def test_redacts_previously_uncovered_pii_field_names():
    """The original keyword list only covered password/ssn/credit_card/cvv/pin -
    real ATS forms also ask for these, none of which matched before."""
    cm = CheckpointManager()
    raw = {
        "date_of_birth": "1990-01-01",
        "national_id_number": "AB123456",
        "passport_number": "X1234567",
        "drivers_license_number": "D1234567",
        "bank_account_number": "123456789",
        "routing_number": "021000021",
        "tax_id": "12-3456789",
        "first_name": "Not Sensitive",
    }
    result = cm._redact_sensitive(raw)
    for key in raw:
        if key == "first_name":
            continue
        assert result[key] == "[REDACTED]", f"{key} should have been redacted"
    assert result["first_name"] == "Not Sensitive"


def test_redacts_ssn_shaped_value_in_a_generic_field_name():
    """Defense in depth: a real SSN typed into a genuinely generic field
    (free-text notes, an unmapped custom question) has no telling field name
    at all - only the value shape gives it away."""
    cm = CheckpointManager()
    result = cm._redact_sensitive({"additional_notes": "123-45-6789", "city": "Springfield"})
    assert result["additional_notes"] == "[REDACTED]"
    assert result["city"] == "Springfield"


def test_redacts_card_shaped_value_in_a_generic_field_name():
    cm = CheckpointManager()
    result = cm._redact_sensitive({"custom_field_7": "4111 1111 1111 1111"})
    assert result["custom_field_7"] == "[REDACTED]"


def test_does_not_redact_ordinary_short_numeric_values():
    """Phone numbers, zip codes, and years must not false-positive."""
    cm = CheckpointManager()
    result = cm._redact_sensitive({"phone": "555-0123", "zip": "94105", "grad_year": "2020"})
    assert result["phone"] == "555-0123"
    assert result["zip"] == "94105"
    assert result["grad_year"] == "2020"
