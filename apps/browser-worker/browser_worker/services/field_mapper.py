import logging
import re
from typing import Optional
from ..models import FormField

logger = logging.getLogger(__name__)


class FieldMapper:
    """Map form fields to canonical names"""

    def __init__(self):
        self.learned_mappings = {}
        self._init_rules()

    def _init_rules(self):
        """Initialize mapping rules"""
        self.rules = [
            # Personal information
            (r"first[\s_-]?name", "first_name"),
            (r"given[\s_-]?name", "first_name"),
            (r"last[\s_-]?name", "last_name"),
            (r"family[\s_-]?name", "last_name"),
            (r"surname", "last_name"),
            # Order matters: checked only after the first/last-name rules
            # above, so a "First Name" field (which also contains the
            # substring "name") still matches the more specific rule first.
            # Covers a single combined name field - increasingly common on
            # real ATS's (e.g. Ashby's `_systemfield_name`) - which
            # ApplicationData doesn't carry directly; get_value_for_field
            # synthesizes it from first_name + last_name.
            # `\b` alone would miss underscore-adjacent field names like
            # "_systemfield_name" or "applicant_name" - Python regex treats
            # `_` as a word character, so there's no boundary between it
            # and "name". Matches the [\s_-] separator style already used
            # by every other rule in this list, for the same reason.
            (r"(?:^|[\s_-])name(?:[\s_-]|$)", "full_name"),
            (r"^email", "email"),
            (r"e[\s_-]?mail", "email"),
            (r"^phone", "phone"),
            (r"telephone", "phone"),
            (r"mobile", "phone"),
            (r"cell", "phone"),
            
            # Professional
            (r"linkedin", "linkedin"),
            (r"linked[\s_-]?in", "linkedin"),
            (r"portfolio", "portfolio_url"),
            (r"website", "website"),
            (r"github", "github"),
            
            # Work authorization
            (r"work[\s_-]?auth", "work_authorization"),
            (r"authorization", "work_authorization"),
            (r"eligible[\s_-]?to[\s_-]?work", "work_authorization"),
            (r"visa", "work_authorization"),
            (r"sponsorship", "sponsorship"),
            
            # Documents
            (r"resume", "resume"),
            (r"cv", "resume"),
            (r"curriculum[\s_-]?vitae", "resume"),
            (r"cover[\s_-]?letter", "cover_letter"),
            
            # Experience
            (r"years[\s_-]?of[\s_-]?experience", "years_experience"),
            (r"experience[\s_-]?years", "years_experience"),
            (r"current[\s_-]?company", "current_company"),
            (r"current[\s_-]?title", "current_title"),
            (r"current[\s_-]?role", "current_title"),
            
            # Other
            (r"why[\s_-]?interested", "interest"),
            (r"why[\s_-]?apply", "interest"),
            (r"motivation", "interest"),
            (r"address", "address"),
            (r"city", "city"),
            # Confirmed live against a real Pinpoint posting (Confluence
            # Technologies): a real field labeled exactly "Town" - a common
            # synonym for "city" (British/international usage) - had no
            # matching rule here at all, fell all the way through to the
            # AI-generated-answer path (see application_question_agent.py's
            # expects_short_answer), and got filled with a full personal-
            # summary-style paragraph instead of a town name.
            (r"town", "city"),
            (r"state", "state"),
            (r"zip", "zip_code"),
            (r"postal", "zip_code"),
            (r"country", "country"),
        ]

    def map_to_canonical(self, field: FormField) -> Optional[str]:
        """
        Map field to canonical name using rules:
        - Label text matching
        - Name/id patterns
        - Learned mappings
        """
        # Check learned mappings first
        field_key = f"{field.name}:{field.label}"
        if field_key in self.learned_mappings:
            return self.learned_mappings[field_key]

        # Try matching label
        label_lower = field.label.lower()
        for pattern, canonical in self.rules:
            if re.search(pattern, label_lower):
                logger.debug(f"Mapped {field.name} to {canonical} via label")
                return canonical

        # Try matching name/id
        name_lower = field.name.lower()
        for pattern, canonical in self.rules:
            if re.search(pattern, name_lower):
                logger.debug(f"Mapped {field.name} to {canonical} via name")
                return canonical

        # Try placeholder
        if field.placeholder:
            placeholder_lower = field.placeholder.lower()
            for pattern, canonical in self.rules:
                if re.search(pattern, placeholder_lower):
                    logger.debug(f"Mapped {field.name} to {canonical} via placeholder")
                    return canonical

        logger.debug(f"No mapping found for field {field.name}")
        return None

    def learn_mapping(self, field: FormField, canonical_name: str):
        """Store a learned mapping"""
        field_key = f"{field.name}:{field.label}"
        self.learned_mappings[field_key] = canonical_name
        logger.info(f"Learned mapping: {field_key} -> {canonical_name}")

    def get_value_for_field(
        self, field: FormField, application_data: dict
    ) -> Optional[str]:
        """Get value from application data for field"""
        # First try canonical mapping
        canonical = self.map_to_canonical(field)
        if canonical == "full_name":
            # Not a literal key on ApplicationData - synthesized instead of
            # falling through to the AI-agent path, which (confirmed live
            # against a real Ashby posting, AI_PROVIDER=mock) filled a real
            # applicant's name field with the mock gateway's canned
            # placeholder text rather than their actual name.
            full_name = f"{application_data.get('first_name') or ''} {application_data.get('last_name') or ''}".strip()
            if full_name:
                return full_name
        elif canonical and canonical in application_data:
            return application_data[canonical]

        # Try direct field name match
        if field.name in application_data:
            return application_data[field.name]

        # Try custom fields
        custom = application_data.get("custom_fields")
        if custom and field.name in custom:
            return custom[field.name]

        return None
