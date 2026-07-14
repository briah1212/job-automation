import logging
from playwright.async_api import Page
from .base import ATSAdapter
from ..models import (
    ApplicationForm,
    FormField,
    FillResult,
    UploadResult,
    NavigationResult,
    SubmissionResult,
    ConfirmationResult,
)

logger = logging.getLogger(__name__)


class GenericAdapter(ATSAdapter):
    """Fallback adapter for unknown ATS systems"""

    async def detect(self, page: Page) -> bool:
        """Always returns True as fallback"""
        return True

    async def inspect_form(self, page: Page) -> ApplicationForm:
        """Extract generic form schema"""
        fields = []
        
        # Find all form inputs
        form = await page.query_selector("form")
        if not form:
            raise ValueError("No form found on page")

        inputs = await form.query_selector_all("input, select, textarea")
        
        for input_elem in inputs:
            name = await input_elem.get_attribute("name")
            input_id = await input_elem.get_attribute("id")
            
            if not name and not input_id:
                continue

            identifier = name or input_id
            input_type = await input_elem.get_attribute("type") or "text"
            tag_name = await input_elem.evaluate("el => el.tagName.toLowerCase()")
            
            if tag_name == "select":
                input_type = "select"
            elif tag_name == "textarea":
                input_type = "textarea"

            # Skip submit buttons
            if input_type in ["submit", "button"]:
                continue

            required = await input_elem.get_attribute("required") is not None
            placeholder = await input_elem.get_attribute("placeholder")

            # Try to find label
            label_text = identifier.replace("_", " ").replace("-", " ").title()
            try:
                if input_id:
                    label_elem = await page.query_selector(f'label[for="{input_id}"]')
                    if label_elem:
                        label_text = await label_elem.text_content()
            except:
                pass

            # Get options for select
            options = None
            if input_type == "select":
                option_elems = await input_elem.query_selector_all("option")
                options = []
                for opt in option_elems:
                    value = await opt.get_attribute("value")
                    if value:
                        options.append(value)

            selector = f'[name="{name}"]' if name else f'#{input_id}'
            
            fields.append(
                FormField(
                    name=identifier,
                    label=label_text.strip() if label_text else identifier,
                    input_type=input_type,
                    required=required,
                    options=options,
                    placeholder=placeholder,
                    selector=selector,
                )
            )

        # Find submit button
        submit_btn = await form.query_selector('[type="submit"]')
        submit_text = "Submit"
        if submit_btn:
            submit_text = await submit_btn.text_content() or "Submit"

        return ApplicationForm(
            page_number=1,
            total_pages=1,
            fields=fields,
            submit_button_text=submit_text.strip(),
        )

    async def fill_field(self, page: Page, field: FormField, value: str) -> FillResult:
        """Fill a single field"""
        try:
            selector = field.selector
            
            if field.input_type == "select":
                await page.select_option(selector, value)
            elif field.input_type == "textarea":
                await page.fill(selector, value)
            elif field.input_type == "file":
                return FillResult(
                    success=False,
                    field=field.name,
                    error="Use upload_document for file fields",
                )
            else:
                await page.fill(selector, value)

            logger.info(f"Filled field {field.name}")
            return FillResult(success=True, field=field.name, value=value)

        except Exception as e:
            logger.error(f"Error filling field {field.name}: {e}")
            return FillResult(success=False, field=field.name, error=str(e))

    async def upload_document(
        self, page: Page, field: FormField, file_path: str
    ) -> UploadResult:
        """Upload file"""
        try:
            await page.set_input_files(field.selector, file_path)
            logger.info(f"Uploaded file to {field.name}")
            return UploadResult(success=True, field=field.name, file_path=file_path)

        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return UploadResult(
                success=False, field=field.name, file_path=file_path, error=str(e)
            )

    async def navigate_next(self, page: Page) -> NavigationResult:
        """Click next/continue - generic implementation"""
        return NavigationResult(
            success=False,
            page_number=1,
            url=page.url,
            error="Generic adapter does not support multi-page navigation",
        )

    async def submit(self, page: Page) -> SubmissionResult:
        """Final submit"""
        try:
            submit_btn = await page.query_selector('[type="submit"]')
            if not submit_btn:
                return SubmissionResult(success=False, error="Submit button not found")

            current_url = page.url
            await submit_btn.click()
            
            # Wait for navigation or response
            await page.wait_for_timeout(2000)
            
            new_url = page.url
            logger.info(f"Submitted form, URL: {current_url} -> {new_url}")
            
            return SubmissionResult(success=True, redirect_url=new_url)

        except Exception as e:
            logger.error(f"Error submitting: {e}")
            return SubmissionResult(success=False, error=str(e))

    async def detect_confirmation(self, page: Page) -> ConfirmationResult:
        """Generic confirmation detection"""
        try:
            body_text = await page.text_content("body")
            body_lower = body_text.lower()
            
            # Look for common confirmation keywords
            confirmation_keywords = [
                "thank you",
                "submitted successfully",
                "application received",
                "confirmation",
                "we'll be in touch",
            ]
            
            confidence = 0.0
            for keyword in confirmation_keywords:
                if keyword in body_lower:
                    confidence += 0.3
            
            confidence = min(confidence, 1.0)
            confirmed = confidence >= 0.5
            
            if confirmed:
                logger.info(f"Detected possible confirmation page (confidence: {confidence})")
            
            return ConfirmationResult(
                confirmed=confirmed,
                confidence=confidence,
                message="Generic confirmation detection",
            )

        except Exception as e:
            logger.error(f"Error detecting confirmation: {e}")
            return ConfirmationResult(confirmed=False, confidence=0.0)

    def get_name(self) -> str:
        return "Generic"
