"""Regression test: FieldMapper must recognize "Town" as a synonym for
"city", not leave it unmapped.

CRITICAL finding, confirmed live against a real Pinpoint posting
(Confluence Technologies): a real field labeled exactly "Town" had no
matching rule (only "city" was covered), so map_to_canonical returned
None and the field fell all the way through to the AI-generated-answer
path. The agent's prompt had no length constraint appropriate for a
single-line field, so it produced a full personal-summary-style paragraph
("Brian Hsu, email hsubrian1212@gmail.com, phone 646-236-7795,
LinkedIn...") for what needed to be a single town/city name - a real
application field ended up with completely wrong, nonsensical content.
"""
from browser_worker.models import FormField
from browser_worker.services.field_mapper import FieldMapper

_APP_DATA = {
    "first_name": "Brian",
    "last_name": "Hsu",
    "city": "Ann Arbor",
}


def test_town_field_maps_to_city_canonical():
    field = FormField(name="application_form[application][town]", label="Town", input_type="text", required=True, selector="[name=town]")
    mapper = FieldMapper()

    assert mapper.map_to_canonical(field) == "city"
    assert mapper.get_value_for_field(field, _APP_DATA) == "Ann Arbor"


def test_city_field_still_maps_correctly():
    """The new "town" rule must not regress the existing "city" rule."""
    field = FormField(name="city", label="City", input_type="text", required=True, selector="[name=city]")
    mapper = FieldMapper()

    assert mapper.map_to_canonical(field) == "city"
    assert mapper.get_value_for_field(field, _APP_DATA) == "Ann Arbor"
