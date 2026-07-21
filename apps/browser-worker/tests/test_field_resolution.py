"""Pure unit tests for field_resolution.py - no browser, no network, fast."""
from browser_worker.models import FormField
from browser_worker.services.field_resolution import _constrain_to_options, compute_form_fingerprint


def _select_field(name="willing_to_relocate", options="__default__"):
    # NB: options=[] must mean "no options", distinct from options=None meaning
    # "use the default" - `options or [...]` would silently treat [] as falsy
    # and substitute the default, which is exactly the mistake this comment
    # exists to prevent reintroducing.
    if options == "__default__":
        options = ["yes", "no"]
    return FormField(
        name=name,
        label="Are you willing to relocate?",
        input_type="select",
        required=True,
        options=options,
        selector=f'[name="{name}"]',
    )


class TestConstrainToOptions:
    def test_exact_match_passthrough(self):
        assert _constrain_to_options("yes", _select_field()) == "yes"

    def test_case_insensitive_exact_match(self):
        assert _constrain_to_options("YES", _select_field()) == "yes"

    def test_substring_match(self):
        field = _select_field(options=["job_board", "referral", "other"])
        assert _constrain_to_options("I found it on a job board", field) == "job_board"

    def test_yes_boolean_heuristic(self):
        assert _constrain_to_options("Yes, I'd be happy to relocate", _select_field()) == "yes"

    def test_no_boolean_heuristic(self):
        assert _constrain_to_options("No, I am not willing to relocate", _select_field()) == "no"

    def test_unrecognizable_answer_returns_none(self):
        assert _constrain_to_options("Mock response generated successfully.", _select_field()) is None

    def test_non_select_field_passes_through_raw(self):
        text_field = FormField(name="interest", label="Interest", input_type="textarea", selector='[name="interest"]')
        assert _constrain_to_options("Anything at all", text_field) == "Anything at all"

    def test_select_with_no_options_passes_through_raw(self):
        field = _select_field(options=[])
        assert _constrain_to_options("Anything at all", field) == "Anything at all"


class TestComputeFormFingerprint:
    def test_same_fields_same_fingerprint_regardless_of_order(self):
        a = compute_form_fingerprint(["first_name", "last_name", "email"])
        b = compute_form_fingerprint(["email", "first_name", "last_name"])
        assert a == b

    def test_different_fields_different_fingerprint(self):
        a = compute_form_fingerprint(["first_name", "last_name"])
        b = compute_form_fingerprint(["first_name", "last_name", "phone"])
        assert a != b

    def test_stable_and_deterministic(self):
        assert compute_form_fingerprint(["a", "b"]) == compute_form_fingerprint(["b", "a"])

    def test_returns_short_hex_string(self):
        fp = compute_form_fingerprint(["first_name"])
        assert len(fp) == 16
        int(fp, 16)  # raises if not valid hex
