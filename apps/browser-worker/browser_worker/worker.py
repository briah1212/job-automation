import logging
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from .models import ApplicationData, Checkpoint
from .adapters import MockATSAdapter, GenericAdapter
from .services import FormInspector, FieldMapper, CheckpointManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class BrowserWorker:
    """Main browser automation worker"""

    def __init__(
        self,
        headless: bool = True,
        checkpoint_dir: str = "/tmp/checkpoints",
        assisted_mode: bool = True,
    ):
        self.headless = headless
        self.assisted_mode = assisted_mode
        self.checkpoint_manager = CheckpointManager(checkpoint_dir)
        self.field_mapper = FieldMapper()
        self.form_inspector = FormInspector()
        
        # Register adapters (order matters - specific first, generic last)
        self.adapters = [
            MockATSAdapter(),
            GenericAdapter(),  # Fallback
        ]

    async def process_application(
        self,
        application_id: str,
        application_url: str,
        application_data: ApplicationData,
    ) -> dict:
        """
        Main workflow:
        1. Get application from API
        2. Launch browser context
        3. Detect ATS type
        4. Select adapter
        5. Navigate to application URL
        6. Inspect form
        7. Fill fields
        8. Upload resume
        9. Create checkpoint
        10. Pause for user approval (assisted mode)
        11. Submit on approval
        12. Detect confirmation
        13. Update application status
        """
        session_id = f"app_{application_id}"
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            )
            page = await context.new_page()

            try:
                # Navigate to application URL
                logger.info(f"Navigating to {application_url}")
                await page.goto(application_url, wait_until="networkidle", timeout=30000)
                
                # Create initial checkpoint
                await self.checkpoint_manager.create_checkpoint(
                    session_id=session_id,
                    page=page,
                    step="initial",
                    filled_fields={},
                    page_number=1,
                )

                # Detect ATS type
                adapter = await self._detect_adapter(page)
                logger.info(f"Using adapter: {adapter.get_name()}")

                # Main application loop
                result = await self._fill_application(
                    page=page,
                    adapter=adapter,
                    application_data=application_data,
                    session_id=session_id,
                )

                return result

            except Exception as e:
                logger.error(f"Error processing application: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e),
                    "session_id": session_id,
                }

            finally:
                await context.close()
                await browser.close()

    async def resume_from_checkpoint(
        self,
        session_id: str,
        application_url: str,
        application_data: ApplicationData,
    ) -> dict:
        """Resume from saved checkpoint"""
        checkpoint = await self.checkpoint_manager.load_checkpoint(session_id)
        
        if not checkpoint:
            return {
                "success": False,
                "error": f"No checkpoint found for session {session_id}",
            }

        logger.info(f"Resuming from checkpoint: {checkpoint.step}")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 720},
            )
            page = await context.new_page()

            try:
                # Navigate to checkpoint URL
                await page.goto(checkpoint.url, wait_until="networkidle", timeout=30000)
                
                # Detect adapter
                adapter = await self._detect_adapter(page)
                
                # Continue from checkpoint
                if checkpoint.step == "ready_to_submit":
                    # Submit the application
                    logger.info("Submitting application")
                    result = await adapter.submit(page)
                    
                    if result.success:
                        # Detect confirmation
                        await page.wait_for_timeout(2000)
                        confirmation = await adapter.detect_confirmation(page)
                        
                        await self.checkpoint_manager.create_checkpoint(
                            session_id=session_id,
                            page=page,
                            step="submitted",
                            filled_fields=checkpoint.filled_fields,
                            page_number=checkpoint.page_number,
                        )
                        
                        return {
                            "success": True,
                            "confirmed": confirmation.confirmed,
                            "application_id": confirmation.application_id,
                            "session_id": session_id,
                        }
                    else:
                        return {
                            "success": False,
                            "error": result.error,
                            "session_id": session_id,
                        }
                else:
                    return {
                        "success": False,
                        "error": f"Cannot resume from step: {checkpoint.step}",
                        "session_id": session_id,
                    }

            finally:
                await context.close()
                await browser.close()

    async def _detect_adapter(self, page: Page):
        """Detect which adapter can handle this page"""
        for adapter in self.adapters:
            if await adapter.detect(page):
                return adapter
        
        # Should never reach here since GenericAdapter always returns True
        return self.adapters[-1]

    async def _fill_application(
        self,
        page: Page,
        adapter,
        application_data: ApplicationData,
        session_id: str,
    ) -> dict:
        """Fill multi-page application form"""
        filled_fields = {}
        current_page = 1
        app_data_dict = application_data.model_dump()

        while True:
            # Inspect current form page
            logger.info(f"Inspecting form page {current_page}")
            form = await adapter.inspect_form(page)
            
            logger.info(f"Found {len(form.fields)} fields on page {form.page_number}/{form.total_pages}")

            # Fill each field
            for field in form.fields:
                # Skip file uploads for now
                if field.input_type == "file":
                    continue

                # Get value for field
                value = self.field_mapper.get_value_for_field(field, app_data_dict)
                
                if value is None:
                    logger.warning(f"No value found for field: {field.name} ({field.label})")
                    continue

                # Fill field
                result = await adapter.fill_field(page, field, str(value))
                
                if result.success:
                    filled_fields[field.name] = value
                else:
                    logger.error(f"Failed to fill {field.name}: {result.error}")

            # Handle file uploads
            for field in form.fields:
                if field.input_type == "file":
                    if field.name == "resume" and application_data.resume_path:
                        result = await adapter.upload_document(
                            page, field, application_data.resume_path
                        )
                        if result.success:
                            filled_fields[field.name] = application_data.resume_path
                        else:
                            logger.error(f"Failed to upload resume: {result.error}")

            # Create checkpoint after filling page
            await self.checkpoint_manager.create_checkpoint(
                session_id=session_id,
                page=page,
                step=f"page_{current_page}_filled",
                filled_fields=filled_fields,
                page_number=current_page,
            )

            # Check if this is the last page
            if current_page >= form.total_pages:
                break

            # Navigate to next page
            logger.info("Navigating to next page")
            nav_result = await adapter.navigate_next(page)
            
            if not nav_result.success:
                return {
                    "success": False,
                    "error": f"Failed to navigate: {nav_result.error}",
                    "session_id": session_id,
                }

            current_page = nav_result.page_number
            await page.wait_for_timeout(1000)

        # All pages filled - create checkpoint before submission
        await self.checkpoint_manager.create_checkpoint(
            session_id=session_id,
            page=page,
            step="ready_to_submit",
            filled_fields=filled_fields,
            page_number=current_page,
        )

        # If assisted mode, pause here
        if self.assisted_mode:
            logger.info("Assisted mode: Waiting for approval to submit")
            return {
                "success": True,
                "status": "awaiting_approval",
                "session_id": session_id,
                "message": "Application filled. Waiting for user approval to submit.",
            }

        # Auto-submit mode
        logger.info("Submitting application")
        submit_result = await adapter.submit(page)
        
        if not submit_result.success:
            return {
                "success": False,
                "error": submit_result.error,
                "session_id": session_id,
            }

        # Wait for confirmation page
        await page.wait_for_timeout(2000)
        confirmation = await adapter.detect_confirmation(page)

        # Final checkpoint
        await self.checkpoint_manager.create_checkpoint(
            session_id=session_id,
            page=page,
            step="submitted",
            filled_fields=filled_fields,
            page_number=current_page,
        )

        return {
            "success": True,
            "confirmed": confirmation.confirmed,
            "application_id": confirmation.application_id,
            "confidence": confirmation.confidence,
            "session_id": session_id,
        }


async def main():
    """Example usage"""
    worker = BrowserWorker(headless=False, assisted_mode=True)
    
    # Example application data
    app_data = ApplicationData(
        application_id="test_001",
        first_name="John",
        last_name="Doe",
        email="john.doe@example.com",
        phone="555-0123",
        linkedin="https://linkedin.com/in/johndoe",
        work_authorization="yes",
        resume_path="/tmp/resume.pdf",
        interest="I am excited about this opportunity to contribute to your team.",
    )
    
    result = await worker.process_application(
        application_id="test_001",
        application_url="http://localhost:8080",
        application_data=app_data,
    )
    
    print(f"Result: {result}")


if __name__ == "__main__":
    asyncio.run(main())
