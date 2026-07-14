from abc import ABC, abstractmethod
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
