from __future__ import annotations

from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy.orm import Session

from app.models import Profile, ProfileFact, ResumeFamily, ResumeStatus, ResumeVersion

# Alternate key names to check for each fact type, in priority order.
_SUMMARY_KEYS = ["summary"]
_SKILLS_KEYS = ["skills"]
_EXPERIENCE_KEYS = ["experience"]
_BULLET_KEYS = ["bullets", "highlights", "bullet_points"]


def extract_facts_for_user(db: Session, user_id: UUID) -> List[ProfileFact]:
    """Return the user's ProfileFact rows, extracting them heuristically on first use.

    If the user already has ProfileFact rows, they are returned as-is. Otherwise this
    performs a simple, best-effort heuristic extraction from the user's Profile and any
    resume versions' parsed_data, persisting new ProfileFact rows as it goes.

    This is intentionally a simple heuristic, not a real parser.
    """
    existing = (
        db.query(ProfileFact)
        .filter(ProfileFact.user_id == user_id)
        .all()
    )
    if existing:
        return existing

    created: List[ProfileFact] = []

    profile = db.query(Profile).filter(Profile.user_id == user_id).first()
    if profile is not None:
        created.extend(_extract_from_profile(user_id, profile))

    resume_families = db.query(ResumeFamily).filter(ResumeFamily.user_id == user_id).all()
    resume_family_ids = [family.id for family in resume_families]

    resume_versions: List[ResumeVersion] = []
    if resume_family_ids:
        resume_versions = (
            db.query(ResumeVersion)
            .filter(
                ResumeVersion.family_id.in_(resume_family_ids),
                ResumeVersion.status == ResumeStatus.approved,
            )
            .all()
        )

    for version in resume_versions:
        parsed_data: Dict[str, Any] = version.parsed_data or {}
        if not parsed_data:
            continue

        created.extend(_extract_from_parsed_data(user_id, version.id, parsed_data))

    for fact in created:
        db.add(fact)

    if created:
        db.commit()
        for fact in created:
            db.refresh(fact)

    return created


def _extract_from_profile(user_id: UUID, profile: Profile) -> List[ProfileFact]:
    """Turn the structured Profile fields into facts the Q&A agent can cite.

    Without this, the only fact ever generated was career_interests - every
    other Profile field (name, email, phone, linkedin, work authorization,
    etc.) was correctly filled in by the user but invisible to
    ApplicationQuestionAgent's strictly-grounded prompt, which only sees
    ProfileFact rows. That was masked for a long time by the mock AI
    provider always returning a canned response regardless of input; a real
    provider honestly reported "the provided facts do not contain the
    applicant's full legal name" for a profile that plainly has one.
    """
    facts: List[ProfileFact] = []

    def add(fact_type: str, content: str) -> None:
        facts.append(
            _make_fact(
                user_id=user_id,
                fact_type=fact_type,
                content=content,
                source_type="user_input",
                source_identifier=None,
            )
        )

    if profile.legal_name:
        add("contact_info", f"Full legal name: {profile.legal_name}")
    if profile.preferred_name:
        add("contact_info", f"Preferred name: {profile.preferred_name}")
    if profile.email:
        add("contact_info", f"Email address: {profile.email}")
    if profile.phone:
        add("contact_info", f"Phone number: {profile.phone}")
    if profile.linkedin:
        add("contact_info", f"LinkedIn profile: {profile.linkedin}")
    if profile.github:
        add("contact_info", f"GitHub profile: {profile.github}")
    if profile.city or profile.state or profile.country:
        location = ", ".join(part for part in [profile.city, profile.state, profile.country] if part)
        add("contact_info", f"Current location: {location}")

    if profile.career_interests:
        add("summary_point", profile.career_interests)
    if profile.work_authorization:
        add("summary_point", f"Work authorization status: {profile.work_authorization}")
    if profile.citizenship:
        add("summary_point", f"Citizenship: {profile.citizenship}")
    if profile.target_seniority:
        add("summary_point", f"Target seniority level: {profile.target_seniority}")
    if profile.graduation_year:
        add("summary_point", f"Graduation year: {profile.graduation_year}")
    if profile.relocation_willingness:
        add("summary_point", f"Willingness to relocate: {profile.relocation_willingness}")
    if profile.salary_expectation_min or profile.salary_expectation_max:
        lo = profile.salary_expectation_min
        hi = profile.salary_expectation_max
        if lo and hi:
            add("summary_point", f"Salary expectations: ${lo:,} - ${hi:,}")
        else:
            add("summary_point", f"Salary expectations: ${(lo or hi):,}")
    if profile.clearance_eligible is not None:
        add("summary_point", f"Security clearance eligible: {'Yes' if profile.clearance_eligible else 'No'}")

    return facts


def _extract_from_parsed_data(
    user_id: UUID, resume_version_id: UUID, parsed_data: Dict[str, Any]
) -> List[ProfileFact]:
    facts: List[ProfileFact] = []
    source_identifier = str(resume_version_id)

    # Summary
    for key in _SUMMARY_KEYS:
        value = parsed_data.get(key)
        if isinstance(value, str) and value.strip():
            facts.append(
                _make_fact(
                    user_id=user_id,
                    fact_type="summary_point",
                    content=value.strip(),
                    source_type="resume_upload",
                    source_identifier=source_identifier,
                )
            )
            break

    # Skills
    for key in _SKILLS_KEYS:
        value = parsed_data.get(key)
        if isinstance(value, list):
            for skill in value:
                if isinstance(skill, str) and skill.strip():
                    facts.append(
                        _make_fact(
                            user_id=user_id,
                            fact_type="skill",
                            content=skill.strip(),
                            source_type="resume_upload",
                            source_identifier=source_identifier,
                        )
                    )
            break

    # Experience bullets
    for key in _EXPERIENCE_KEYS:
        value = parsed_data.get(key)
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, dict):
                    continue
                bullets = None
                for bullet_key in _BULLET_KEYS:
                    candidate = item.get(bullet_key)
                    if isinstance(candidate, list):
                        bullets = candidate
                        break
                if not bullets:
                    continue
                for bullet in bullets:
                    if isinstance(bullet, str) and bullet.strip():
                        facts.append(
                            _make_fact(
                                user_id=user_id,
                                fact_type="experience_bullet",
                                content=bullet.strip(),
                                source_type="resume_upload",
                                source_identifier=source_identifier,
                            )
                        )
            break

    return facts


def _make_fact(
    user_id: UUID,
    fact_type: str,
    content: str,
    source_type: str,
    source_identifier: str | None,
) -> ProfileFact:
    return ProfileFact(
        user_id=user_id,
        fact_type=fact_type,
        content=content,
        source_type=source_type,
        source_identifier=source_identifier,
        confidence=0.8,
        user_verified=False,
        permitted_uses=[],
    )
