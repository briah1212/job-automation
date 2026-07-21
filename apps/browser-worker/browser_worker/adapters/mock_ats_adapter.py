import logging
from typing import Tuple
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
from ..state import BrowserState, RunContext, StateHandlerResult
from ..services.credential_vault_client import get_or_create_credential
from ..services.field_resolution import compute_form_fingerprint, resolve_field_value

logger = logging.getLogger(__name__)

_HASH_STATE_MAP = {
    "": BrowserState.LANDING,
    "/apply": BrowserState.APPLY,
    "/login": BrowserState.LOGIN,
    "/signup": BrowserState.CREATE_ACCOUNT,
    "/verify-email": BrowserState.EMAIL_VERIFICATION,
    "/profile-setup": BrowserState.PROFILE_SETUP,
    "/resume-upload": BrowserState.RESUME_UPLOAD,
    "/resume-parsing": BrowserState.RESUME_PARSE_WAIT,
}


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
            elif field.input_type == "checkbox":
                # page.fill() doesn't work on checkboxes at all - it needs
                # check()/uncheck(), driven by truthiness of the given value.
                if str(value).strip().lower() in ("true", "1", "yes", "on"):
                    await page.check(selector)
                else:
                    await page.uncheck(selector)
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

            # Click next button - must scope to the currently visible page,
            # since query_selector("button.next-btn") alone always resolves
            # to the first (page 1) button in DOM order even when it's hidden.
            visible_page = await page.query_selector(f'.form-page[data-page="{current_page}"]')
            next_btn = await visible_page.query_selector("button.next-btn") if visible_page else None
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

            if new_page == current_page:
                # Click landed but the page didn't advance - client-side
                # validation blocked it (e.g. an unfilled required field).
                error_el = await page.query_selector("#error-message")
                error_text = await error_el.text_content() if error_el else None
                return NavigationResult(
                    success=False,
                    page_number=current_page,
                    url=page.url,
                    error=(error_text or "Page did not advance after clicking next").strip(),
                )

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
            # #submit-btn is a unique id, unlike button[type="submit"] - the
            # fixture now has five submit buttons (login/signup/profile-setup/
            # resume-upload/application), so an unscoped type-selector would
            # silently grab the wrong one.
            submit_btn = await page.query_selector("#submit-btn")
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

    # -- State machine layer --

    async def detect_state(self, page: Page) -> Tuple[BrowserState, float]:
        """Exact-hash detection - legitimate for an ATS-specific adapter that
        knows this site's own routing scheme (the same way a real WorkdayAdapter
        would key off Workday's own URL patterns), unlike GenericAdapter's
        signal-scoring fallback."""
        url = page.url
        if "confirmation.html" in url:
            return BrowserState.SUBMITTED, 1.0

        fragment = url.split("#", 1)[1] if "#" in url else ""
        fragment = "" if fragment in ("", "/") else "/" + fragment.lstrip("/")

        if fragment == "/application":
            page_indicator = await page.text_content("#page-indicator")
            on_review_page = bool(page_indicator and "Page 3" in page_indicator)
            if not on_review_page:
                return BrowserState.APPLICATION, 1.0
            try:
                terms_checked = await page.is_checked('[name="terms"]')
            except Exception:
                terms_checked = False
            return (BrowserState.SUBMIT_READY if terms_checked else BrowserState.REVIEW), 1.0

        mapped = _HASH_STATE_MAP.get(fragment)
        if mapped is not None:
            return mapped, 1.0
        return BrowserState.UNKNOWN, 0.0

    async def handle_state(self, state: BrowserState, page: Page, ctx: RunContext) -> StateHandlerResult:
        handlers = {
            BrowserState.LANDING: self._handle_landing,
            BrowserState.APPLY: self._handle_apply,
            BrowserState.LOGIN: self._handle_login,
            BrowserState.CREATE_ACCOUNT: self._handle_create_account,
            BrowserState.PROFILE_SETUP: self._handle_profile_setup,
            BrowserState.RESUME_UPLOAD: self._handle_resume_upload,
            BrowserState.RESUME_PARSE_WAIT: self._handle_resume_parse_wait,
            BrowserState.APPLICATION: self._handle_application_page,
            BrowserState.REVIEW: self._handle_review,
        }
        handler = handlers.get(state)
        if handler is None:
            return StateHandlerResult(success=False, error=f"No handler for state {state.value}")
        return await handler(page, ctx)

    async def _handle_landing(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        await page.click("#apply-btn")
        return StateHandlerResult(success=True)

    async def _handle_apply(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        """Vault-first: reuse a working credential via login; otherwise attempt
        automatic account creation. Never silently retries a credential that's
        already known to be broken - see docs/browser-state-machine-design.md
        section 8 ("Reconciling with spec.md Example C")."""
        try:
            credential = await get_or_create_credential(
                user_id=ctx.user_id,
                ats_platform=ctx.ats_platform,
                tenant_key=ctx.tenant_key,
                email=ctx.application_data.email,
            )
        except Exception as exc:
            return StateHandlerResult(success=False, error=f"Credential vault lookup failed: {exc}")

        ctx.credential = credential
        if credential["status"] != "active":
            return StateHandlerResult(
                success=False,
                error=f"Existing credential for this tenant is in state '{credential['status']}' - not safe to retry automatically",
            )

        if credential["created"]:
            await page.click("#show-signup-btn")
        else:
            await page.click("#show-login-btn")
        return StateHandlerResult(success=True)

    async def _handle_login(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        if not ctx.credential:
            return StateHandlerResult(success=False, error="No credential available for login")

        await page.fill('[name="login_email"]', ctx.credential["email"])
        await page.fill('[name="login_password"]', ctx.credential["password"])
        await page.click('#login-form button[type="submit"]')
        await page.wait_for_timeout(300)

        error_el = await page.query_selector("#error-message")
        if error_el and await error_el.is_visible():
            error_text = (await error_el.text_content() or "").strip()
            return StateHandlerResult(success=False, error=f"Login failed: {error_text}")
        return StateHandlerResult(success=True)

    async def _handle_create_account(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        if not ctx.credential:
            return StateHandlerResult(success=False, error="No credential available for account creation")

        await page.fill('[name="signup_email"]', ctx.credential["email"])
        await page.fill('[name="signup_password"]', ctx.credential["password"])
        await page.fill('[name="signup_confirm_password"]', ctx.credential["password"])
        await page.click('#signup-form button[type="submit"]')
        await page.wait_for_timeout(300)

        error_el = await page.query_selector("#error-message")
        if error_el and await error_el.is_visible():
            error_text = (await error_el.text_content() or "").strip()
            return StateHandlerResult(success=False, error=f"Account creation failed: {error_text}")
        return StateHandlerResult(success=True)

    async def _handle_profile_setup(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        try:
            await page.fill('[name="preferred_name"]', ctx.application_data.first_name)
        except Exception:
            pass
        try:
            await page.select_option('[name="referral_source"]', "job_board")
        except Exception as exc:
            return StateHandlerResult(success=False, error=f"Could not fill profile setup: {exc}")

        await page.click('#profile-setup-form button[type="submit"]')
        return StateHandlerResult(success=True)

    async def _handle_resume_upload(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        if not ctx.application_data.resume_path:
            return StateHandlerResult(success=False, error="No resume_path available to upload")
        try:
            await page.set_input_files('#resume-upload-form [name="resume"]', ctx.application_data.resume_path)
        except Exception as exc:
            return StateHandlerResult(success=False, error=f"Resume upload failed: {exc}")

        await page.click('#resume-upload-form button[type="submit"]')
        return StateHandlerResult(success=True)

    async def _handle_resume_parse_wait(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        # Nothing to do - the fixture auto-advances after a simulated delay.
        # The control loop's _wait_for_transition handles waiting for that.
        return StateHandlerResult(success=True)

    async def _handle_application_page(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        """Fill the current APPLICATION page and advance - generalized from the
        old _fill_application loop, now one page per state-machine transition
        instead of a dedicated inner while-loop."""
        form = await self.inspect_form(page)
        app_data_dict = ctx.application_data.model_dump()
        form_fingerprint = compute_form_fingerprint([f.name for f in form.fields])

        for field in form.fields:
            if field.input_type == "file":
                continue
            value = await resolve_field_value(field, ctx, app_data_dict, form_fingerprint)
            if ctx.pending_question:
                return StateHandlerResult(success=True)
            if value is None:
                continue
            result = await self.fill_field(page, field, str(value))
            if result.success:
                ctx.filled_fields[field.name] = value
            else:
                logger.error(f"Failed to fill {field.name}: {result.error}")

        nav_result = await self.navigate_next(page)
        if not nav_result.success:
            return StateHandlerResult(success=False, error=f"Failed to advance past application page: {nav_result.error}")
        ctx.current_page = nav_result.page_number
        return StateHandlerResult(success=True)

    async def _handle_review(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        """Fill any remaining review-page fields and check the required
        attestation checkbox. Checking it is safe here specifically because
        SUBMIT_READY still pauses for an explicit human approve-submit action
        before anything is actually sent - that click is the real consent gate,
        this just gets the form into a submittable state for the human to see."""
        form = await self.inspect_form(page)
        app_data_dict = ctx.application_data.model_dump()
        form_fingerprint = compute_form_fingerprint([f.name for f in form.fields])

        for field in form.fields:
            if field.input_type == "checkbox":
                result = await self.fill_field(page, field, "true")
                if result.success:
                    ctx.filled_fields[field.name] = True
                continue
            value = await resolve_field_value(field, ctx, app_data_dict, form_fingerprint)
            if ctx.pending_question:
                return StateHandlerResult(success=True)
            if value is None:
                continue
            result = await self.fill_field(page, field, str(value))
            if result.success:
                ctx.filled_fields[field.name] = value

        return StateHandlerResult(success=True)
