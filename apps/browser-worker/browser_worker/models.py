from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class FormField(BaseModel):
    name: str
    label: str
    input_type: str  # text, email, tel, select, file, textarea, radio, checkbox
    required: bool = False
    options: Optional[list[str]] = None
    placeholder: Optional[str] = None
    canonical_name: Optional[str] = None
    selector: str  # CSS selector to locate the field


class ApplicationForm(BaseModel):
    page_number: int
    total_pages: int
    fields: list[FormField]
    submit_button_text: str
    next_button_text: Optional[str] = None


class FillResult(BaseModel):
    success: bool
    field: str
    value: Optional[str] = None
    error: Optional[str] = None


class UploadResult(BaseModel):
    success: bool
    field: str
    file_path: str
    error: Optional[str] = None


class NavigationResult(BaseModel):
    success: bool
    page_number: int
    url: str
    error: Optional[str] = None


class SubmissionResult(BaseModel):
    success: bool
    error: Optional[str] = None
    redirect_url: Optional[str] = None


class ConfirmationResult(BaseModel):
    confirmed: bool
    application_id: Optional[str] = None
    confidence: float
    message: Optional[str] = None


class Checkpoint(BaseModel):
    session_id: str
    timestamp: datetime
    step: str
    url: str
    screenshot_path: str
    filled_fields: dict
    form_state: dict
    page_number: int


class ApplicationData(BaseModel):
    application_id: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    work_authorization: str
    resume_path: str
    interest: Optional[str] = None
    custom_fields: Optional[dict] = None
