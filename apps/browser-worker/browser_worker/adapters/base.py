from abc import ABC, abstractmethod
from typing import Tuple
from playwright.async_api import Page
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


class ATSAdapter(ABC):
    """Base adapter for ATS-specific form handling"""

    @abstractmethod
    async def detect(self, page: Page) -> bool:
        """Can this adapter handle this page?"""
        pass

    @abstractmethod
    async def inspect_form(self, page: Page) -> ApplicationForm:
        """Extract form schema"""
        pass

    @abstractmethod
    async def fill_field(self, page: Page, field: FormField, value: str) -> FillResult:
        """Fill a single field"""
        pass

    @abstractmethod
    async def upload_document(
        self, page: Page, field: FormField, file_path: str
    ) -> UploadResult:
        """Upload file"""
        pass

    @abstractmethod
    async def navigate_next(self, page: Page) -> NavigationResult:
        """Click next/continue"""
        pass

    @abstractmethod
    async def submit(self, page: Page) -> SubmissionResult:
        """Final submit"""
        pass

    @abstractmethod
    async def detect_confirmation(self, page: Page) -> ConfirmationResult:
        """Is this a confirmation page?"""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Adapter name for logging"""
        pass

    # -- State machine layer, built on top of the primitives above --

    @abstractmethod
    async def detect_state(self, page: Page) -> Tuple[BrowserState, float]:
        """Classify the current page as a BrowserState with a confidence score in [0, 1].

        Must combine multiple signals (URL, headings, buttons, form structure)
        rather than a single selector - see GenericAdapter for the reference
        multi-signal implementation. Return (BrowserState.UNKNOWN, score) when
        not confident rather than guessing.
        """
        pass

    @abstractmethod
    async def handle_state(self, state: BrowserState, page: Page, ctx: RunContext) -> StateHandlerResult:
        """Take whatever action advances past `state` (click Apply, fill+submit
        login, etc). Dispatches internally to per-state handler methods -
        callers only need this one entry point."""
        pass
