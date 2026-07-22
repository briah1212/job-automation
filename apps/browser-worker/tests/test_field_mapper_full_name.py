"""Regression test: FieldMapper must resolve a single combined "name" field
from first_name + last_name, instead of leaving it unmapped.

Found live against a real Ashby posting during production validation
(docs/browser-state-machine-design.md): Ashby's field is literally named
`_systemfield_name` - no rule matched it (only split first_name/last_name
patterns existed), so map_to_canonical returned None and the field fell
through to the AI-agent path. With AI_PROVIDER=mock in this environment,
that filled a real applicant's name field with the mock gateway's canned
placeholder text ("Mock response generated successfully.") instead of
their actual name - in production, it would call a real LLM to guess a
name instead of using the one already on file, which is worse than simply
wrong.
"""
from browser_worker.models import FormField
from browser_worker.services.field_mapper import FieldMapper

_APP_DATA = {
    "first_name": "Brian",
    "last_name": "Hsu",
    "email": "hsubrian1212@gmail.com",
}


def test_full_name_field_resolves_via_label():
    field = FormField(name="_systemfield_name", label="Name", input_type="text", required=True, selector="[name=_systemfield_name]")
    mapper = FieldMapper()

    assert mapper.map_to_canonical(field) == "full_name"
    assert mapper.get_value_for_field(field, _APP_DATA) == "Brian Hsu"


def test_first_name_field_still_maps_to_first_name_not_full_name():
    """The bare "name" rule must not shadow the more specific first/last
    rules - order in the rule list is what keeps this correct."""
    field = FormField(name="first_name", label="First Name", input_type="text", required=True, selector="[name=first_name]")
    mapper = FieldMapper()

    assert mapper.map_to_canonical(field) == "first_name"
    assert mapper.get_value_for_field(field, _APP_DATA) == "Brian"


def test_full_name_field_resolves_via_field_name_when_label_missing():
    field = FormField(name="applicant_name", label="applicant_name", input_type="text", required=True, selector="[name=applicant_name]")
    mapper = FieldMapper()

    assert mapper.get_value_for_field(field, _APP_DATA) == "Brian Hsu"


def test_username_field_is_not_mistaken_for_full_name():
    """"username" (login credential, unrelated concept) must not match just
    because it contains the substring "name" with no separator."""
    field = FormField(name="username", label="Username", input_type="text", required=True, selector="[name=username]")
    mapper = FieldMapper()

    assert mapper.map_to_canonical(field) != "full_name"
