"""
Integration tests for file processing across providers.

These tests require actual API keys and test the real file processing capabilities.
"""

import os
import tempfile

import pytest
from llmbridge.file_utils import analyze_image, create_image_content
from llmbridge.schemas import LLMRequest, Message
from llmbridge.service import LLMBridge
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def create_test_image_with_text() -> str:
    """Create a test image with readable text and return the file path."""
    # Create image with clear text
    img = Image.new("RGB", (400, 200), color="white")
    draw = ImageDraw.Draw(img)

    # Use a clear, readable font
    try:
        # Try to use a system font
        font = ImageFont.truetype("Arial.ttf", 24)
    except:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 24)
        except:
            font = ImageFont.load_default()

    # Draw clear, simple text
    text_lines = ["FILE TEST: ID-001", "Name: John Doe", "Status: ACTIVE"]

    y_position = 40
    for line in text_lines:
        draw.text((50, y_position), line, fill="black", font=font)
        y_position += 40

    # Save to temporary file
    temp_fd, temp_path = tempfile.mkstemp(suffix=".png")
    os.close(temp_fd)
    img.save(temp_path, "PNG")

    return temp_path


def create_test_pdf_with_text() -> str:
    """Create a test PDF with readable text and return the file path."""
    temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
    os.close(temp_fd)

    # Create PDF with clear, simple content
    c = canvas.Canvas(temp_path, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica", 14)

    content_lines = [
        "Test Document for LLM Processing",
        "",
        "Document ID: PDF-TEST-001",
        "Name: John Doe",
        "Email: john.doe@example.com",
        "",
        "This document tests file processing capabilities.",
        "Please extract the ID and name from this document.",
    ]

    y_position = height - 100
    for line in content_lines:
        c.drawString(100, y_position, line)
        y_position -= 25

    c.save()
    return temp_path


@pytest.mark.integration
class TestFileProcessing:
    """Clean integration tests for file processing across providers."""

    @pytest.fixture
    def service(self):
        """Create LLM service for testing."""
        return LLMBridge(enable_db_logging=False)

    @pytest.fixture
    def test_image_path(self):
        """Create a test image file."""
        image_path = create_test_image_with_text()
        yield image_path
        # Cleanup
        if os.path.exists(image_path):
            os.unlink(image_path)

    @pytest.fixture
    def test_pdf_path(self):
        """Create a test PDF file."""
        pdf_path = create_test_pdf_with_text()
        yield pdf_path
        # Cleanup
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)

    @pytest.mark.asyncio
    async def test_image_analysis_with_openai(self, service, test_image_path):
        """Test image analysis with OpenAI GPT-4o."""
        available_models = service.get_available_models()
        if (
            not available_models.get("openai")
            or "gpt-4o" not in available_models["openai"]
        ):
            pytest.skip("OpenAI GPT-4o not available")

        # Use our utility function
        content = analyze_image(
            test_image_path,
            "Extract the text from this image, especially the ID and name.",
        )

        request = LLMRequest(
            messages=[Message(role="user", content=content)],
            model="gpt-4o",
            max_tokens=200,
        )

        response = await service.chat(request)

        # Verify response
        assert response.content is not None
        assert len(response.content) > 0

        # Check if key information was extracted
        content_lower = response.content.lower()
        assert "id-001" in content_lower
        assert "john doe" in content_lower

        print(f"OpenAI extracted: {response.content}")

    @pytest.mark.asyncio
    async def test_image_analysis_with_anthropic(self, service, test_image_path):
        """Test image analysis with Anthropic Claude."""
        available_models = service.get_available_models()
        if not available_models.get("anthropic"):
            pytest.skip("Anthropic not available")

        content = analyze_image(
            test_image_path,
            "Extract the text from this image, especially the ID and name.",
        )

        request = LLMRequest(
            messages=[Message(role="user", content=content)],
            model="claude-3-5-sonnet-20241022",
            max_tokens=200,
        )

        response = await service.chat(request)

        # Verify response
        assert response.content is not None
        assert len(response.content) > 0

        # Check if key information was extracted
        content_lower = response.content.lower()
        assert "id-001" in content_lower
        assert "john doe" in content_lower

        print(f"Anthropic extracted: {response.content}")

    @pytest.mark.asyncio
    async def test_image_analysis_with_google(self, service, test_image_path):
        """Test image analysis with Google Gemini."""
        available_models = service.get_available_models()
        if not available_models.get("google"):
            pytest.skip("Google not available")

        content = analyze_image(
            test_image_path,
            "Extract the text from this image, especially the ID and name.",
        )

        request = LLMRequest(
            messages=[Message(role="user", content=content)],
            model="gemini-1.5-flash",
            max_tokens=200,
        )

        response = await service.chat(request)

        # Verify response
        assert response.content is not None
        assert len(response.content) > 0

        # Check if key information was extracted
        content_lower = response.content.lower()
        assert "id-001" in content_lower
        assert "john doe" in content_lower

        print(f"Google extracted: {response.content}")

    @pytest.mark.asyncio
    async def test_pdf_processing_anthropic(self, service, test_pdf_path):
        """Test PDF processing with Anthropic using universal file interface."""
        available_models = service.get_available_models()
        if not available_models.get("anthropic"):
            pytest.skip("Anthropic not available")

        # Use the universal file interface
        from llmbridge.file_utils import analyze_file

        content = analyze_file(
            test_pdf_path,
            "Extract the text from this PDF document, especially the ID and name.",
        )

        request = LLMRequest(
            messages=[Message(role="user", content=content)],
            model="claude-3-5-sonnet-20241022",
            max_tokens=300,
        )

        response = await service.chat(request)

        # Verify response contains key information
        content_lower = response.content.lower()
        assert "pdf-test-001" in content_lower
        assert "john doe" in content_lower

        print(f"PDF processing with Anthropic: {response.content}")

    @pytest.mark.asyncio
    async def test_pdf_processing_google(self, service, test_pdf_path):
        """Test PDF processing with Google using universal file interface."""
        available_models = service.get_available_models()
        if not available_models.get("google"):
            pytest.skip("Google not available")

        # Use the universal file interface
        from llmbridge.file_utils import analyze_file

        content = analyze_file(
            test_pdf_path,
            "Extract the text from this PDF document, especially the ID and name.",
        )

        request = LLMRequest(
            messages=[Message(role="user", content=content)],
            model="gemini-1.5-flash",
            max_tokens=300,
        )

        response = await service.chat(request)

        # Verify response contains key information
        content_lower = response.content.lower()
        assert "pdf-test-001" in content_lower
        assert "john doe" in content_lower

        print(f"PDF processing with Google: {response.content}")

    @pytest.mark.asyncio
    async def test_pdf_processing_openai(self, service, test_pdf_path):
        """Test PDF processing with OpenAI using Assistants API automatically."""
        available_models = service.get_available_models()
        if not available_models.get("openai"):
            pytest.skip("OpenAI not available")

        # Use the universal file interface
        from llmbridge.file_utils import analyze_file

        content = analyze_file(
            test_pdf_path,
            "Extract the text from this PDF document, especially the ID and name.",
        )

        request = LLMRequest(
            messages=[Message(role="user", content=content)],
            model="gpt-4o",  # Will automatically use Assistants API for PDFs
            max_tokens=300,
        )

        try:
            response = await service.chat(request)

            # Verify response contains key information
            content_lower = response.content.lower()
            assert "pdf-test-001" in content_lower
            assert "john doe" in content_lower

            print(f"PDF processing with OpenAI: {response.content}")

        except Exception as e:
            # Handle potential API limitations
            error_str = str(e).lower()
            if any(
                term in error_str
                for term in ["billing", "quota", "usage limit", "rate limit"]
            ):
                import pytest

                pytest.skip(f"OpenAI API limit reached: {e}")
            elif "assistants" in error_str:
                import pytest

                pytest.skip(f"Assistants API not available: {e}")
            else:
                raise

    @pytest.mark.asyncio
    async def test_file_utility_functions(self, service, test_image_path):
        """Test that file utility functions work correctly."""
        from llmbridge.file_utils import (
            create_data_url,
            encode_file_to_base64,
            get_file_mime_type,
            validate_image_file,
        )

        # Test file utilities
        assert validate_image_file(test_image_path) is True
        assert get_file_mime_type(test_image_path) == "image/png"

        # Test encoding
        base64_data = encode_file_to_base64(test_image_path)
        assert len(base64_data) > 0

        # Test data URL creation
        data_url = create_data_url(test_image_path)
        assert data_url.startswith("data:image/png;base64,")

        # Test content creation
        content = create_image_content(test_image_path, "Test image")
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"

        print("All file utility functions work correctly!")

    @pytest.mark.asyncio
    async def test_url_handling(self, service):
        """Test that URLs are handled correctly."""
        # Test with httpbin image endpoint
        test_url = "https://httpbin.org/image/png"

        content = analyze_image(test_url, "Describe this image")

        # Verify URL was passed through correctly (no base64 conversion)
        assert content[1]["image_url"]["url"] == test_url

        print("URL handling works correctly!")
