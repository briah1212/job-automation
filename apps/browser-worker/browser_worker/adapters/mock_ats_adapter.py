import logging
from playwright.async_api import Page, TimeoutError as PlaywrightTimeout
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


class MockATSAdapter(ATSAdapter):
    """Adapter for Mock ATS test site"""

    async def detect(self, page: Page) -> bool:
        """Detect by checking for data-ats="mock" attribute"""
        try:
            element = await page.query_selector('html[data-ats="mock"]')
            return element is not None
        except Exception as e:
            logger.error(f"Error detecting Mock ATS: {e}")
            return False

    async def inspect_form(self, page: Page) -> ApplicationForm:
        """Extract form schema from current visible page"""
        # Get current page number
        page_indicator = await page.text_content("#page-indicator")
        page_num, total = 1, 3
        if page_indicator:
            parts = page_indicator.split()
            if len(parts) >= 4:  # "Page 1 of 3"
                page_num = int(parts[1])
                total = int(parts[3])

        # Find visible form page
        visible_page = await page.query_selector(f'.form-page[data-page="{page_num}"]')
        if not visible_page:
            raise ValueError(f"Could not find page {page_num}")

        # Extract fields from visible page
        fields = []
        inputs = await visible_page.query_selector_all("input, select, textarea")
        
        for input_elem in inputs:
            name = await input_elem.get_attribute("name")
            if not name:  # Skip buttons
                continue

            input_type = await input_elem.get_attribute("type") or "text"
            tag_name = await input_elem.evaluate("el => el.tagName.toLowerCase()")
            
            if tag_name == "select":
                input_type = "select"
            elif tag_name == "textarea":
                input_type = "textarea"

            required = await input_elem.get_attribute("required") is not None
            placeholder = await input_elem.get_attribute("placeholder")

            # Find label
            label_text = name.replace("_", " ").title()
            try:
                label_elem = await visible_page.query_selector(f'label:has(+ *[name="{name}"])')
                if not label_elem:
                    # Try finding label that contains the input
                    label_elem = await visible_page.query_selector(f'label:has([name="{name}"])')
                if label_elem:
                    label_text = await label_elem.text_content()
                    label_text = label_text.strip().replace(" *", "")
            except:
                pass

            # Get options for select
            options = None
            if input_type == "select":
                option_elems = await input_elem.query_selector_all("option")
                options = []
                for opt in option_elems:
                    value = await opt.get_attribute("value")
                    if value:  # Skip empty placeholder options
                        options.append(value)

            fields.append(
                FormField(
                    name=name,
                    label=label_text,
                    input_type=input_type,
                    required=required,
                    options=options,
                    placeholder=placeholder,
                    selector=f'[name="{name}"]',
                )
            )

        # Determine button text
        submit_btn = await visible_page.query_selector('button[type="submit"]')
        next_btn = await visible_page.query_selector('button.next-btn')
        
        submit_text = "Submit Application"
        next_text = None
        
        if submit_btn:
            submit_text = await submit_btn.text_content()
        if next_btn:
            next_text = await next_btn.text_content()

        return ApplicationForm(
            page_number=page_num,
            total_pages=total,
            fields=fields,
            submit_button_text=submit_text.strip() if submit_text else "Submit",
            next_button_text=next_text.strip() if next_text else None,
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
                # Handle file upload separately
                return FillResult(
                    success=False,
                    field=field.name,
                    error="Use upload_document for file fields",
                )
            else:
                await page.fill(selector, value)

            logger.info(f"Filled field {field.name} with value: {value}")
            return FillResult(success=True, field=field.name, value=value)

        except Exception as e:
            logger.error(f"Error filling field {field.name}: {e}")
            return FillResult(success=False, field=field.name, error=str(e))

    async def upload_document(
        self, page: Page, field: FormField, file_path: str
    ) -> UploadResult:
        """Upload file"""
        try:
            selector = field.selector
            await page.set_input_files(selector, file_path)
            logger.info(f"Uploaded file {file_path} to field {field.name}")
            return UploadResult(success=True, field=field.name, file_path=file_path)

        except Exception as e:
            logger.error(f"Error uploading file to {field.name}: {e}")
            return UploadResult(
                success=False, field=field.name, file_path=file_path, error=str(e)
            )

    async def navigate_next(self, page: Page) -> NavigationResult:
        """Click next/continue"""
        try:
            # Get current page number before navigation
            page_indicator = await page.text_content("#page-indicator")
            current_page = 1
            if page_indicator:
                parts = page_indicator.split()
                if len(parts) >= 2:
                    current_page = int(parts[1])

            # Click next button
            next_btn = await page.query_selector("button.next-btn")
            if not next_btn:
                return NavigationResult(
                    success=False,
                    page_number=current_page,
                    url=page.url,
                    error="Next button not found",
                )

            await next_btn.click()
            
            # Wait for page transition
            await page.wait_for_timeout(500)
            
            # Get new page number
            page_indicator = await page.text_content("#page-indicator")
            new_page = current_page + 1
            if page_indicator:
                parts = page_indicator.split()
                if len(parts) >= 2:
                    new_page = int(parts[1])

            logger.info(f"Navigated from page {current_page} to {new_page}")
            return NavigationResult(
                success=True, page_number=new_page, url=page.url
            )

        except Exception as e:
            logger.error(f"Error navigating to next page: {e}")
            return NavigationResult(
                success=False, page_number=current_page, url=page.url, error=str(e)
            )

    async def submit(self, page: Page) -> SubmissionResult:
        """Final submit"""
        try:
            submit_btn = await page.query_selector('button[type="submit"]')
            if not submit_btn:
                return SubmissionResult(success=False, error="Submit button not found")

            # Click submit and wait for navigation
            await submit_btn.click()
            
            try:
                await page.wait_for_url("**/confirmation.html", timeout=10000)
            except PlaywrightTimeout:
                # Check if we're on confirmation page anyway
                if "confirmation" not in page.url:
                    return SubmissionResult(
                        success=False, error="Did not navigate to confirmation page"
                    )

            logger.info(f"Submitted application, redirected to {page.url}")
            return SubmissionResult(success=True, redirect_url=page.url)

        except Exception as e:
            logger.error(f"Error submitting application: {e}")
            return SubmissionResult(success=False, error=str(e))

    async def detect_confirmation(self, page: Page) -> ConfirmationResult:
        """Is this a confirmation page?"""
        try:
            # Check for confirmation text
            body_text = await page.text_content("body")
            
            if "Application Submitted Successfully" in body_text:
                # Extract application ID
                app_id = None
                app_id_elem = await page.query_selector("#app-id")
                if app_id_elem:
                    app_id = await app_id_elem.text_content()

                logger.info(f"Detected confirmation page with ID: {app_id}")
                return ConfirmationResult(
                    confirmed=True,
                    application_id=app_id,
                    confidence=1.0,
                    message="Application Submitted Successfully",
                )

            return ConfirmationResult(confirmed=False, confidence=0.0)

        except Exception as e:
            logger.error(f"Error detecting confirmation: {e}")
            return ConfirmationResult(confirmed=False, confidence=0.0)

    def get_name(self) -> str:
        return "MockATS"
