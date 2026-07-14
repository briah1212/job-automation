import pytest
from playwright.async_api import async_playwright
from browser_worker.models import ApplicationData
from browser_worker.adapters import MockATSAdapter, GenericAdapter
from browser_worker.worker import BrowserWorker


class TestMockATSAdapter:
    """Test Mock ATS adapter"""

    @pytest.fixture
    async def mock_ats_page(self):
        """Setup browser and navigate to mock ATS"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            # Assumes mock ATS is running on localhost:8080
            await page.goto("http://localhost:8080", wait_until="networkidle")
            yield page
            await browser.close()

    @pytest.mark.asyncio
    async def test_detect_mock_ats(self, mock_ats_page):
        """Test detection of Mock ATS"""
        adapter = MockATSAdapter()
        detected = await adapter.detect(mock_ats_page)
        assert detected is True

    @pytest.mark.asyncio
    async def test_inspect_form_page1(self, mock_ats_page):
        """Test form inspection on page 1"""
        adapter = MockATSAdapter()
        form = await adapter.inspect_form(mock_ats_page)
        
        assert form.page_number == 1
        assert form.total_pages == 3
        assert len(form.fields) == 5  # first_name, last_name, email, phone, linkedin
        
        # Check field names
        field_names = [f.name for f in form.fields]
        assert "first_name" in field_names
        assert "last_name" in field_names
        assert "email" in field_names

    @pytest.mark.asyncio
    async def test_fill_field(self, mock_ats_page):
        """Test filling a field"""
        adapter = MockATSAdapter()
        form = await adapter.inspect_form(mock_ats_page)
        
        # Find first_name field
        first_name_field = next(f for f in form.fields if f.name == "first_name")
        
        # Fill field
        result = await adapter.fill_field(mock_ats_page, first_name_field, "John")
        
        assert result.success is True
        assert result.field == "first_name"
        
        # Verify field value
        value = await mock_ats_page.input_value('[name="first_name"]')
        assert value == "John"

    @pytest.mark.asyncio
    async def test_navigate_next(self, mock_ats_page):
        """Test navigation to next page"""
        adapter = MockATSAdapter()
        
        # Fill required fields on page 1
        await mock_ats_page.fill('[name="first_name"]', "John")
        await mock_ats_page.fill('[name="last_name"]', "Doe")
        await mock_ats_page.fill('[name="email"]', "john@example.com")
        
        # Navigate to next page
        result = await adapter.navigate_next(mock_ats_page)
        
        assert result.success is True
        assert result.page_number == 2

    @pytest.mark.asyncio
    async def test_upload_document(self, mock_ats_page):
        """Test file upload (requires navigating to page 2)"""
        adapter = MockATSAdapter()
        
        # Navigate to page 2
        await mock_ats_page.fill('[name="first_name"]', "John")
        await mock_ats_page.fill('[name="last_name"]', "Doe")
        await mock_ats_page.fill('[name="email"]', "john@example.com")
        await mock_ats_page.click("button.next-btn")
        await mock_ats_page.wait_for_timeout(500)
        
        # Inspect page 2 form
        form = await adapter.inspect_form(mock_ats_page)
        
        # Find resume field
        resume_field = next(f for f in form.fields if f.name == "resume")
        
        # Create a test PDF file
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pdf", delete=False) as f:
            f.write("%PDF-1.4\nTest PDF")
            test_file = f.name
        
        # Upload file
        result = await adapter.upload_document(mock_ats_page, resume_field, test_file)
        
        assert result.success is True
        assert result.field == "resume"


class TestGenericAdapter:
    """Test Generic adapter"""

    @pytest.mark.asyncio
    async def test_detect_always_true(self):
        """Generic adapter should always return True for detect"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content("<html><body><form></form></body></html>")
            
            adapter = GenericAdapter()
            detected = await adapter.detect(page)
            
            assert detected is True
            await browser.close()


class TestBrowserWorker:
    """Test full browser worker workflow"""

    @pytest.mark.asyncio
    async def test_process_application_assisted_mode(self):
        """Test processing application in assisted mode"""
        worker = BrowserWorker(headless=True, assisted_mode=True)
        
        # Create test resume
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pdf", delete=False) as f:
            f.write("%PDF-1.4\nTest Resume")
            resume_path = f.name
        
        # Application data
        app_data = ApplicationData(
            application_id="test_001",
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            phone="555-0123",
            linkedin="https://linkedin.com/in/johndoe",
            work_authorization="yes",
            resume_path=resume_path,
            interest="I am very interested in this role.",
        )
        
        # Process application
        result = await worker.process_application(
            application_id="test_001",
            application_url="http://localhost:8080",
            application_data=app_data,
        )
        
        assert result["success"] is True
        assert result["status"] == "awaiting_approval"
        assert "session_id" in result

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint(self):
        """Test resuming from checkpoint"""
        worker = BrowserWorker(headless=True, assisted_mode=True)
        
        # Create test resume
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pdf", delete=False) as f:
            f.write("%PDF-1.4\nTest Resume")
            resume_path = f.name
        
        # Application data
        app_data = ApplicationData(
            application_id="test_002",
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
            phone="555-0456",
            work_authorization="yes",
            resume_path=resume_path,
        )
        
        # First, create a checkpoint
        result1 = await worker.process_application(
            application_id="test_002",
            application_url="http://localhost:8080",
            application_data=app_data,
        )
        
        session_id = result1["session_id"]
        
        # Resume from checkpoint
        result2 = await worker.resume_from_checkpoint(
            session_id=session_id,
            application_url="http://localhost:8080",
            application_data=app_data,
        )
        
        assert result2["success"] is True
        assert result2.get("confirmed") is not None
