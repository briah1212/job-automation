"""Regression test: ExtractedJob must not crash when the model honestly
reports it found nothing to extract.

Confirmed live testing a real Oracle Recruiting Cloud posting (Akamai):
the specific job had expired ("This job is no longer available"), so the
raw text fed to the extraction agent contained no real job posting at
all. The model correctly returned null for company/title rather than
hallucinating fake values - but validating a required `str` field against
None raised an uncaught pydantic ValidationError, crashing the entire
extraction task instead of leaving the job gracefully unresolved (which
worker.py's own `if job.company and job.title` gate already handles
correctly, if only it could actually reach that check).
"""
from app.ai_gateway.schemas import ExtractedJob


def test_none_company_and_title_coerce_to_empty_string_not_a_crash():
    result = ExtractedJob.model_validate({
        "company": None,
        "title": None,
        "location": None,
    })
    assert result.company == ""
    assert result.title == ""


def test_real_values_are_unaffected():
    result = ExtractedJob.model_validate({
        "company": "Akamai",
        "title": "Senior II Software Engineer",
    })
    assert result.company == "Akamai"
    assert result.title == "Senior II Software Engineer"
