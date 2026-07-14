import logging
from typing import Optional, List
from playwright.async_api import Page
from ..models import FormField

logger = logging.getLogger(__name__)


class FormInspector:
    """Extract form fields with context"""

    async def extract_fields(self, page: Page) -> List[FormField]:
        """
        Extract all form fields with:
        - Label text
        - Input name/id
        - Input type
        - Required state
        - Options (for select/radio)
        - Placeholder
        - Nearby headings for context
        """
        fields = []
        
        # Find all forms on page
        forms = await page.query_selector_all("form")
        if not forms:
            logger.warning("No forms found on page")
            return fields

        for form in forms:
            inputs = await form.query_selector_all("input, select, textarea")
            
            for input_elem in inputs:
                try:
                    field = await self._extract_field(page, form, input_elem)
                    if field:
                        fields.append(field)
                except Exception as e:
                    logger.error(f"Error extracting field: {e}")
                    continue

        logger.info(f"Extracted {len(fields)} fields from page")
        return fields

    async def _extract_field(
        self, page: Page, form, input_elem
    ) -> Optional[FormField]:
        """Extract a single field"""
        name = await input_elem.get_attribute("name")
        input_id = await input_elem.get_attribute("id")
        
        if not name and not input_id:
            return None

        identifier = name or input_id
        input_type = await input_elem.get_attribute("type") or "text"
        tag_name = await input_elem.evaluate("el => el.tagName.toLowerCase()")
        
        if tag_name == "select":
            input_type = "select"
        elif tag_name == "textarea":
            input_type = "textarea"

        # Skip buttons
        if input_type in ["submit", "button", "reset"]:
            return None

        required = await input_elem.get_attribute("required") is not None
        placeholder = await input_elem.get_attribute("placeholder")

        # Find label - try multiple strategies
        label_text = await self._find_label(page, input_elem, identifier, input_id)
        
        # Get context from nearby headings
        context = await self._get_context(input_elem)

        # Get options for select/radio
        options = None
        if input_type == "select":
            options = await self._extract_select_options(input_elem)
        elif input_type == "radio":
            options = await self._extract_radio_options(form, name)

        selector = f'[name="{name}"]' if name else f'#{input_id}'
        
        return FormField(
            name=identifier,
            label=label_text,
            input_type=input_type,
            required=required,
            options=options,
            placeholder=placeholder,
            selector=selector,
        )

    async def _find_label(
        self, page: Page, input_elem, identifier: str, input_id: Optional[str]
    ) -> str:
        """Find label text using multiple strategies"""
        
        # Strategy 1: label[for="id"]
        if input_id:
            try:
                label_elem = await page.query_selector(f'label[for="{input_id}"]')
                if label_elem:
                    text = await label_elem.text_content()
                    if text:
                        return text.strip().replace(" *", "").replace("*", "")
            except:
                pass

        # Strategy 2: parent label
        try:
            parent = await input_elem.evaluate_handle("el => el.parentElement")
            tag = await parent.evaluate("el => el.tagName.toLowerCase()")
            if tag == "label":
                text = await parent.text_content()
                if text:
                    return text.strip().replace(" *", "").replace("*", "")
        except:
            pass

        # Strategy 3: aria-label
        try:
            aria_label = await input_elem.get_attribute("aria-label")
            if aria_label:
                return aria_label.strip()
        except:
            pass

        # Strategy 4: aria-labelledby
        try:
            aria_labelledby = await input_elem.get_attribute("aria-labelledby")
            if aria_labelledby:
                label_elem = await page.query_selector(f'#{aria_labelledby}')
                if label_elem:
                    text = await label_elem.text_content()
                    if text:
                        return text.strip()
        except:
            pass

        # Fallback: format identifier
        return identifier.replace("_", " ").replace("-", " ").title()

    async def _get_context(self, input_elem) -> Optional[str]:
        """Get context from nearby headings"""
        try:
            # Look for nearest heading before this input
            heading = await input_elem.evaluate("""
                el => {
                    let current = el;
                    while (current = current.previousElementSibling) {
                        if (current.matches('h1, h2, h3, h4, h5, h6')) {
                            return current.textContent;
                        }
                    }
                    // Check parent's previous siblings
                    let parent = el.parentElement;
                    if (parent) {
                        current = parent;
                        while (current = current.previousElementSibling) {
                            if (current.matches('h1, h2, h3, h4, h5, h6')) {
                                return current.textContent;
                            }
                        }
                    }
                    return null;
                }
            """)
            return heading.strip() if heading else None
        except:
            return None

    async def _extract_select_options(self, select_elem) -> List[str]:
        """Extract options from select element"""
        options = []
        option_elems = await select_elem.query_selector_all("option")
        
        for opt in option_elems:
            value = await opt.get_attribute("value")
            text = await opt.text_content()
            
            # Skip empty placeholder options
            if value and value.strip():
                options.append(value)
            elif text and text.strip() and text.strip() != "Select...":
                options.append(text.strip())
        
        return options

    async def _extract_radio_options(self, form, name: str) -> List[str]:
        """Extract options from radio button group"""
        options = []
        radio_elems = await form.query_selector_all(f'input[type="radio"][name="{name}"]')
        
        for radio in radio_elems:
            value = await radio.get_attribute("value")
            if value:
                options.append(value)
        
        return options
