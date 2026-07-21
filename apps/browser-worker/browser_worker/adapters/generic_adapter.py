import logging
from typing import List, Optional, Tuple

from playwright.async_api import Page, ElementHandle
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

_NEXT_BUTTON_WORDS = ("next", "continue", "proceed")
_SUBMIT_BUTTON_WORDS = ("submit", "apply", "send application", "finish")


class GenericAdapter(ATSAdapter):
    """Fallback adapter for unknown ATS systems.

    Unlike MockATSAdapter (which can key off this one site's known routing),
    every selector/signal here is generic - no assumption about class names,
    URL structure, or hash routing belonging to any specific ATS. Playwright's
    `:visible` pseudo-class does the DOM-scoping work that a site-specific
    adapter would otherwise need explicit container selectors for (the exact
    class of bug found twice in MockATSAdapter this session - grabbing the
    first same-named element in the DOM regardless of whether it's the one
    actually on screen).
    """

    async def detect(self, page: Page) -> bool:
        """Always returns True as fallback"""
        return True

    async def _find_visible_form(self, page: Page) -> Optional[ElementHandle]:
        return await page.query_selector("form:visible")

    async def inspect_form(self, page: Page) -> ApplicationForm:
        """Extract generic form schema from whichever form is actually visible"""
        fields = []

        form = await self._find_visible_form(page)
        if not form:
            raise ValueError("No visible form found on page")

        inputs = await form.query_selector_all("input:visible, select:visible, textarea:visible")

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

            if input_type in ["submit", "button"]:
                continue

            required = await input_elem.get_attribute("required") is not None
            placeholder = await input_elem.get_attribute("placeholder")

            label_text = identifier.replace("_", " ").replace("-", " ").title()
            try:
                if input_id:
                    label_elem = await page.query_selector(f'label[for="{input_id}"]')
                    if label_elem:
                        label_text = await label_elem.text_content()
            except Exception:
                pass

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

        submit_btn = await form.query_selector('[type="submit"]:visible')
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
            elif field.input_type == "checkbox":
                if str(value).strip().lower() in ("true", "1", "yes", "on"):
                    await page.check(selector)
                else:
                    await page.uncheck(selector)
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

    async def _find_button_by_words(self, page: Page, words: Tuple[str, ...]) -> Optional[ElementHandle]:
        candidates = await page.query_selector_all(
            "button:visible, input[type='submit']:visible, input[type='button']:visible, a:visible"
        )
        for el in candidates:
            text = ((await el.text_content()) or (await el.get_attribute("value")) or "").strip().lower()
            if text and any(word in text for word in words):
                return el
        return None

    async def navigate_next(self, page: Page) -> NavigationResult:
        """Generic next/continue: find a plausibly-labeled control, click it,
        and confirm the page actually changed (not just that the click landed) -
        the same lesson MockATSAdapter's navigate_next bug taught this session,
        applied generically instead of via a known selector."""
        try:
            before_url = page.url
            before_text = await page.text_content("body")

            next_btn = await self._find_button_by_words(page, _NEXT_BUTTON_WORDS)
            if next_btn is None:
                return NavigationResult(success=False, page_number=1, url=page.url, error="No next/continue control found")

            await next_btn.click()
            await page.wait_for_timeout(500)

            after_url = page.url
            after_text = await page.text_content("body")
            if after_url == before_url and after_text == before_text:
                return NavigationResult(success=False, page_number=1, url=page.url, error="Page did not change after clicking next/continue")

            return NavigationResult(success=True, page_number=1, url=page.url)

        except Exception as e:
            logger.error(f"Error navigating: {e}")
            return NavigationResult(success=False, page_number=1, url=page.url, error=str(e))

    async def submit(self, page: Page) -> SubmissionResult:
        """Final submit"""
        try:
            submit_btn = await self._find_button_by_words(page, _SUBMIT_BUTTON_WORDS)
            if not submit_btn:
                return SubmissionResult(success=False, error="Submit button not found")

            current_url = page.url
            await submit_btn.click()
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

    # -- State machine layer: signal-scoring detection, generic handlers --

    async def _gather_signals(self, page: Page) -> dict:
        url = page.url.lower()

        heading_els = await page.query_selector_all("h1:visible, h2:visible")
        headings = [((await el.text_content()) or "").strip().lower() for el in heading_els]

        button_els = await page.query_selector_all(
            "button:visible, input[type='submit']:visible, input[type='button']:visible, a:visible"
        )
        buttons: List[str] = []
        for el in button_els:
            text = ((await el.text_content()) or (await el.get_attribute("value")) or "").strip().lower()
            if text:
                buttons.append(text)

        has_password = (await page.query_selector("input[type='password']:visible")) is not None
        has_confirm_password = (await page.query_selector("input[name*='confirm' i][type='password']:visible")) is not None
        has_file_input = (await page.query_selector("input[type='file']:visible")) is not None
        visible_fields = await page.query_selector_all("input:visible, select:visible, textarea:visible")

        unchecked_required_checkbox = False
        for cb in await page.query_selector_all("input[type='checkbox'][required]:visible"):
            if not await cb.is_checked():
                unchecked_required_checkbox = True
                break

        body_text = ((await page.text_content("body")) or "").lower()

        return {
            "url": url,
            "headings": headings,
            "buttons": buttons,
            "has_password": has_password,
            "has_confirm_password": has_confirm_password,
            "has_file_input": has_file_input,
            "visible_field_count": len(visible_fields),
            "unchecked_required_checkbox": unchecked_required_checkbox,
            "body_text": body_text,
        }

    def _score_landing(self, s: dict) -> float:
        score = 0.0
        if any(b in ("apply", "apply now") for b in s["buttons"]):
            score += 0.6
        if s["visible_field_count"] == 0 and not s["has_password"]:
            score += 0.3
        return min(score, 1.0)

    def _score_apply(self, s: dict) -> float:
        score = 0.0
        has_login_btn = any(w in b for b in s["buttons"] for w in ("log in", "sign in"))
        has_signup_btn = any(w in b for b in s["buttons"] for w in ("create account", "sign up", "register"))
        if has_login_btn and has_signup_btn:
            score += 0.7
        if "apply" in s["url"]:
            score += 0.2
        return min(score, 1.0)

    def _score_login(self, s: dict) -> float:
        score = 0.0
        if s["has_password"] and not s["has_confirm_password"]:
            score += 0.5
        if any(w in s["url"] for w in ("login", "signin", "sign-in")):
            score += 0.2
        if any(w in h for h in s["headings"] for w in ("log in", "login", "sign in")):
            score += 0.2
        if any(w in b for b in s["buttons"] for w in ("log in", "sign in")):
            score += 0.1
        return min(score, 1.0)

    def _score_create_account(self, s: dict) -> float:
        score = 0.0
        if s["has_password"] and s["has_confirm_password"]:
            score += 0.5
        if any(w in s["url"] for w in ("signup", "sign-up", "register", "create-account", "create_account")):
            score += 0.2
        if any(w in h for h in s["headings"] for w in ("create account", "sign up", "register")):
            score += 0.3
        return min(score, 1.0)

    def _score_email_verification(self, s: dict) -> float:
        score = 0.0
        if any(w in s["url"] for w in ("verify", "verification")):
            score += 0.3
        if any(w in s["body_text"] for w in ("check your email", "verify your email", "verification link", "confirm your email")):
            score += 0.6
        return min(score, 1.0)

    def _score_profile_setup(self, s: dict) -> float:
        score = 0.0
        if any(w in s["url"] for w in ("profile-setup", "profile_setup", "onboarding")):
            score += 0.4
        if any(w in h for h in s["headings"] for w in ("profile", "set up your")):
            score += 0.3
        if not s["has_password"] and not s["has_file_input"] and s["visible_field_count"] > 0:
            score += 0.2
        return min(score, 1.0)

    def _score_resume_upload(self, s: dict) -> float:
        score = 0.0
        if s["has_file_input"]:
            score += 0.5
        if any(w in s["url"] for w in ("resume", "cv-upload", "upload")):
            score += 0.2
        if any(w in h for h in s["headings"] for w in ("resume", "upload your resume", "cv")):
            score += 0.3
        return min(score, 1.0)

    def _score_resume_parse_wait(self, s: dict) -> float:
        score = 0.0
        if any(w in s["body_text"] for w in ("parsing", "processing your resume", "please wait")):
            score += 0.6
        if any(w in s["url"] for w in ("parsing", "processing")):
            score += 0.2
        return min(score, 1.0)

    def _score_application(self, s: dict) -> float:
        score = 0.0
        if s["visible_field_count"] >= 2 and not s["has_password"] and not s["has_file_input"]:
            score += 0.4
        if any(w in s["url"] for w in ("application", "apply-form")):
            score += 0.1
        if any(w in b for b in s["buttons"] for w in _NEXT_BUTTON_WORDS):
            score += 0.3
        return min(score, 1.0)

    def _score_review(self, s: dict) -> float:
        score = 0.0
        if s["unchecked_required_checkbox"]:
            score += 0.4
        if any(w in h for h in s["headings"] for w in ("review", "confirm your")):
            score += 0.3
        if any(w in s["buttons"] for w in ("submit", "submit application")) and s["unchecked_required_checkbox"]:
            score += 0.2
        return min(score, 1.0)

    def _score_submit_ready(self, s: dict) -> float:
        if s["unchecked_required_checkbox"]:
            return 0.0
        score = 0.0
        if any(w in b for b in s["buttons"] for w in _SUBMIT_BUTTON_WORDS):
            score += 0.5
        if any(w in h for h in s["headings"] for w in ("review", "confirm")):
            score += 0.2
        return min(score, 1.0)

    async def detect_state(self, page: Page) -> Tuple[BrowserState, float]:
        confirmation = await self.detect_confirmation(page)
        if confirmation.confirmed:
            return BrowserState.SUBMITTED, confirmation.confidence

        signals = await self._gather_signals(page)
        scores = {
            BrowserState.LANDING: self._score_landing(signals),
            BrowserState.APPLY: self._score_apply(signals),
            BrowserState.LOGIN: self._score_login(signals),
            BrowserState.CREATE_ACCOUNT: self._score_create_account(signals),
            BrowserState.EMAIL_VERIFICATION: self._score_email_verification(signals),
            BrowserState.PROFILE_SETUP: self._score_profile_setup(signals),
            BrowserState.RESUME_UPLOAD: self._score_resume_upload(signals),
            BrowserState.RESUME_PARSE_WAIT: self._score_resume_parse_wait(signals),
            BrowserState.APPLICATION: self._score_application(signals),
            BrowserState.REVIEW: self._score_review(signals),
            BrowserState.SUBMIT_READY: self._score_submit_ready(signals),
        }
        best_state, best_score = max(scores.items(), key=lambda kv: kv[1])
        if best_score < 0.5:
            return BrowserState.UNKNOWN, best_score
        return best_state, best_score

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
            return StateHandlerResult(success=False, error=f"No generic handler for state {state.value}")
        return await handler(page, ctx)

    async def _handle_landing(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        btn = await self._find_button_by_words(page, ("apply now", "apply"))
        if not btn:
            return StateHandlerResult(success=False, error="No Apply button found")
        await btn.click()
        return StateHandlerResult(success=True)

    async def _handle_apply(self, page: Page, ctx: RunContext) -> StateHandlerResult:
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

        words = ("create account", "sign up", "register") if credential["created"] else ("log in", "sign in")
        btn = await self._find_button_by_words(page, words)
        if not btn:
            return StateHandlerResult(success=False, error="Could not find login/signup entry point")
        await btn.click()
        return StateHandlerResult(success=True)

    async def _fill_credential_form(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        if not ctx.credential:
            return StateHandlerResult(success=False, error="No credential available")

        form = await self.inspect_form(page)
        password_fields = [f for f in form.fields if f.input_type == "password"]
        confirm_field = next((f for f in password_fields if "confirm" in f.name.lower()), None)
        primary_password_field = next((f for f in password_fields if f is not confirm_field), None)
        email_field = next((f for f in form.fields if f.input_type == "email" or "email" in f.name.lower()), None)

        if email_field:
            await self.fill_field(page, email_field, ctx.credential["email"])
        if primary_password_field:
            await self.fill_field(page, primary_password_field, ctx.credential["password"])
        if confirm_field:
            await self.fill_field(page, confirm_field, ctx.credential["password"])

        submit_btn = await self._find_button_by_words(page, _SUBMIT_BUTTON_WORDS + ("log in", "sign in", "create account"))
        if not submit_btn:
            return StateHandlerResult(success=False, error="No submit control found on credential form")
        await submit_btn.click()
        await page.wait_for_timeout(300)
        return StateHandlerResult(success=True)

    async def _handle_login(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        return await self._fill_credential_form(page, ctx)

    async def _handle_create_account(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        return await self._fill_credential_form(page, ctx)

    async def _handle_profile_setup(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        form = await self.inspect_form(page)
        app_data_dict = ctx.application_data.model_dump()
        for field in form.fields:
            if field.input_type == "file":
                continue
            value = ctx.field_mapper.get_value_for_field(field, app_data_dict)
            if value is None and field.input_type == "select" and field.options:
                value = field.options[0]
            if value is None:
                continue
            await self.fill_field(page, field, str(value))

        submit_btn = await self._find_button_by_words(page, _SUBMIT_BUTTON_WORDS + _NEXT_BUTTON_WORDS)
        if submit_btn:
            await submit_btn.click()
            return StateHandlerResult(success=True)
        return StateHandlerResult(success=False, error="No continue control found on profile setup form")

    async def _handle_resume_upload(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        if not ctx.application_data.resume_path:
            return StateHandlerResult(success=False, error="No resume_path available to upload")

        form = await self.inspect_form(page)
        file_field = next((f for f in form.fields if f.input_type == "file"), None)
        if file_field is None:
            return StateHandlerResult(success=False, error="No file input found for resume upload")

        result = await self.upload_document(page, file_field, ctx.application_data.resume_path)
        if not result.success:
            return StateHandlerResult(success=False, error=result.error)

        submit_btn = await self._find_button_by_words(page, _SUBMIT_BUTTON_WORDS + _NEXT_BUTTON_WORDS)
        if not submit_btn:
            return StateHandlerResult(success=False, error="No continue control found on resume upload form")
        await submit_btn.click()
        return StateHandlerResult(success=True)

    async def _handle_resume_parse_wait(self, page: Page, ctx: RunContext) -> StateHandlerResult:
        return StateHandlerResult(success=True)

    async def _handle_application_page(self, page: Page, ctx: RunContext) -> StateHandlerResult:
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

        nav_result = await self.navigate_next(page)
        if not nav_result.success:
            return StateHandlerResult(success=False, error=f"Failed to advance past application page: {nav_result.error}")
        return StateHandlerResult(success=True)

    async def _handle_review(self, page: Page, ctx: RunContext) -> StateHandlerResult:
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
