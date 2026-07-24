"""Regression test: _strip_html must not leak an attribute's escaped JSON
payload as literal text.

Confirmed live against a real Recruitee posting: a large SPA embeds its
entire hydration payload as one JSON blob in a single tag's attribute,
e.g. <div data-props="{&quot;appConfig&quot;:...}">, correctly
HTML-escaped so it contains no literal `<`/`>` of its own. The old
implementation unescaped entities BEFORE stripping tags - harmless on its
own, but once every &quot; in that multi-hundred-KB JSON string became a
literal `"`, a literal `>` occurring anywhere inside a nested value (a job
description mentioning "C++", a comparison operator, anything) made the
tag-stripping regex's lazy match stop there instead of at the tag's real
closing `>`, leaking the rest of the JSON straight into the "stripped"
output as literal text.
"""
from worker import _strip_html


def test_escaped_json_in_attribute_does_not_leak_as_text():
    html = (
        '<html><body>'
        '<div data-props="{&quot;appConfig&quot;:{&quot;note&quot;:&quot;written in C++&gt;Java&quot;}}">'
        '</div>'
        '<h1>Real Job Title</h1>'
        '<p>Real job description text.</p>'
        '</body></html>'
    )
    result = _strip_html(html)
    assert "appConfig" not in result
    assert "data-props" not in result
    assert "Real Job Title" in result
    assert "Real job description text." in result


def test_real_text_entities_are_still_unescaped():
    html = "<html><body><p>Ben &amp; Jerry&rsquo;s &hellip; ice cream</p></body></html>"
    result = _strip_html(html)
    assert result == "Ben & Jerry’s … ice cream"


def test_script_and_style_content_still_stripped():
    html = (
        "<html><body>"
        "<script>window.__DATA__ = {secret: 1};</script>"
        "<style>.x { color: red; }</style>"
        "<p>Real visible text</p>"
        "</body></html>"
    )
    result = _strip_html(html)
    assert "Real visible text" in result
    assert "__DATA__" not in result
    assert "color: red" not in result
