"""Render a resume version's parsed data to a PDF file."""
from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

if TYPE_CHECKING:
    from app.models.resume import ResumeVersion


def _experience_bullets(item: Any) -> list[str]:
    """Extract a list of bullet strings from a single experience entry.

    An experience entry may be a plain string, or a dict that carries its
    bullet points under a "bullets" or "highlights" key.
    """
    if isinstance(item, str):
        return [item]

    if isinstance(item, dict):
        bullets = item.get("bullets") or item.get("highlights") or []
        if isinstance(bullets, str):
            bullets = [bullets]

        header_parts = [
            item.get("title") or item.get("role"),
            item.get("company"),
            item.get("dates") or item.get("date_range"),
        ]
        header = " - ".join(part for part in header_parts if part)

        result = []
        if header:
            result.append(header)
        result.extend(str(b) for b in bullets if b)
        return result

    return [str(item)]


def render_resume_pdf(resume_version: "ResumeVersion", output_path: str) -> int:
    """Render `resume_version.parsed_data` to a simple single-column PDF.

    Writes the PDF to `output_path` (creating parent directories as needed)
    and returns the number of pages in the rendered document.
    """
    parsed_data: dict = resume_version.parsed_data or {}

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    styles = getSampleStyleSheet()
    story: list[Any] = []

    summary = parsed_data.get("summary", "")
    if summary:
        story.append(Paragraph(summary, styles["BodyText"]))
        story.append(Spacer(1, 12))

    skills = parsed_data.get("skills", [])
    if skills:
        story.append(Paragraph("Skills", styles["Heading2"]))
        story.append(Paragraph(", ".join(str(s) for s in skills), styles["BodyText"]))
        story.append(Spacer(1, 12))

    experience = parsed_data.get("experience", [])
    if experience:
        story.append(Paragraph("Experience", styles["Heading2"]))
        for entry in experience:
            for line in _experience_bullets(entry):
                story.append(
                    ListFlowable(
                        [ListItem(Paragraph(line, styles["BodyText"]))],
                        bulletType="bullet",
                    )
                )
        story.append(Spacer(1, 12))

    if not story:
        # Reportlab refuses to build a document with an empty story.
        story.append(Paragraph("", styles["BodyText"]))

    doc = SimpleDocTemplate(output_path, pagesize=letter)
    doc.build(story)

    # After build() completes, SimpleDocTemplate.page holds the last page
    # number that was written to the canvas.
    page_count = getattr(doc, "page", None)
    if not isinstance(page_count, int) or page_count < 1:
        page_count = 1

    return page_count
