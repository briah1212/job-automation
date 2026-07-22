"""Regression test: ApplicationData must carry logistics facts (city,
state, zip, country, address) so FieldMapper's already-existing canonical
rules for them have something to actually resolve against.

Found live testing a real application reached via LinkedIn: Epic's real
Avature-hosted careers portal asked a legitimate, low-risk "Country"
question that paused the run to ask the user, even though the user's
Profile already had country="USA" on file - ApplicationData (what
FieldMapper actually resolves fields against) never carried the Profile's
logistics fields at all, so there was nothing for the canonical "country"
rule to ever match, regardless of how complete the profile was.
"""
from browser_worker.models import ApplicationData, FormField
from browser_worker.services.field_mapper import FieldMapper


def _make_app_data(**overrides) -> dict:
    base = dict(
        application_id="a1", first_name="Brian", last_name="Hsu",
        email="hsubrian1212@gmail.com", phone="646-236-7795", linkedin="",
        work_authorization="yes", resume_path="/tmp/resume.pdf", interest=None,
        address_line1="140-15 Holly Ave Apt 1C", city="Flushing", state="NY",
        zip_code="11355", country="USA",
    )
    base.update(overrides)
    return ApplicationData(**base).model_dump()


def test_country_field_resolves_from_application_data():
    field = FormField(name="934", label="Country", input_type="select", required=True, selector="#934")
    mapper = FieldMapper()

    assert mapper.get_value_for_field(field, _make_app_data()) == "USA"


def test_city_state_zip_fields_resolve_from_application_data():
    mapper = FieldMapper()
    app_data = _make_app_data()

    city_field = FormField(name="city_field", label="City", input_type="text", required=True, selector="#city_field")
    state_field = FormField(name="state_field", label="State", input_type="text", required=True, selector="#state_field")
    zip_field = FormField(name="zip_field", label="Zip Code", input_type="text", required=True, selector="#zip_field")

    assert mapper.get_value_for_field(city_field, app_data) == "Flushing"
    assert mapper.get_value_for_field(state_field, app_data) == "NY"
    assert mapper.get_value_for_field(zip_field, app_data) == "11355"


def test_missing_logistics_data_still_resolves_to_none_not_an_error():
    """A user who hasn't filled in their address yet must not crash field
    resolution - just correctly find nothing, same as any other unset
    optional profile fact."""
    field = FormField(name="934", label="Country", input_type="select", required=True, selector="#934")
    mapper = FieldMapper()

    app_data = _make_app_data(country=None)
    assert mapper.get_value_for_field(field, app_data) is None
