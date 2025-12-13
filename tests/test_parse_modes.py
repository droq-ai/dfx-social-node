"""Tests for Telegram parse_mode functionality and field mapping."""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dfx.social.telegram.telegram_message import DFXTelegramMessageComponent


class TestParseModes:
    """Test cases for different parse_mode values."""

    def test_parse_mode_validation(self):
        """Test that parse_mode accepts all valid values."""
        valid_modes = ["", "Markdown", "MarkdownV2", "HTML"]

        for mode in valid_modes:
            component = DFXTelegramMessageComponent(
                bot_token="test_token",
                chat_id="test_chat",
                message_text="Test message",
                parse_mode=mode
            )

            validation = component._validate_inputs()
            assert validation["valid"], f"parse_mode '{mode}' should be valid"

    def test_parse_mode_validation_invalid(self):
        """Test that invalid parse_mode values are rejected."""
        invalid_modes = ["invalid", "markdown", "Html", "MARKDOWNV2"]

        for mode in invalid_modes:
            component = DFXTelegramMessageComponent(
                bot_token="test_token",
                chat_id="test_chat",
                message_text="Test message",
                parse_mode=mode
            )

            validation = component._validate_inputs()
            assert not validation["valid"], f"parse_mode '{mode}' should be invalid"

    def test_field_mapping_message_text_to_text(self):
        """Test that message_text field is properly mapped to text."""
        component = DFXTelegramMessageComponent(
            bot_token="test_token",
            chat_id="test_chat",
            message_text="Hello from client"
        )

        assert component.text == "Hello from client"
        assert component.parse_mode == ""  # Default empty

    def test_field_mapping_preview_and_silent(self):
        """Test that alternative field names work."""
        component = DFXTelegramMessageComponent(
            bot_token="test_token",
            chat_id="test_chat",
            message_text="Test",
            disable_preview="true",
            silent="false"
        )

        assert component.disable_web_page_preview is True
        assert component.disable_notification is False

    def test_parse_mode_none_conversion(self):
        """Test that 'None' parse_mode is converted to empty string."""
        component = DFXTelegramMessageComponent(
            bot_token="test_token",
            chat_id="test_chat",
            message_text="Test",
            parse_mode="None"
        )

        assert component.parse_mode == ""

    def test_html_formatting_support(self):
        """Test that HTML formatting is preserved."""
        html_content = "<b>Bold</b> and <i>italic</i> text"

        component = DFXTelegramMessageComponent(
            bot_token="test_token",
            chat_id="test_chat",
            message_text=html_content,
            parse_mode="HTML"
        )

        assert component.text == html_content
        assert component.parse_mode == "HTML"

        validation = component._validate_inputs()
        assert validation["valid"]

    def test_markdownv2_formatting_support(self):
        """Test that MarkdownV2 formatting is preserved."""
        md_content = "*Bold* and _italic_ text with `code`"

        component = DFXTelegramMessageComponent(
            bot_token="test_token",
            chat_id="test_chat",
            message_text=md_content,
            parse_mode="MarkdownV2"
        )

        assert component.text == md_content
        assert component.parse_mode == "MarkdownV2"

        validation = component._validate_inputs()
        assert validation["valid"]

    def test_client_format_compatibility(self):
        """Test that client field format works end-to-end."""
        client_payload = {
            "bot_token": "test_bot_token",
            "chat_id": "test_chat_id",
            "message_text": "<b>Hello</b> from client",
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
            "disable_notification": True
        }

        component = DFXTelegramMessageComponent(**client_payload)

        # Verify all fields mapped correctly
        assert component.bot_token == "test_bot_token"
        assert component.chat_id == "test_chat_id"
        assert component.text == "<b>Hello</b> from client"
        assert component.parse_mode == "HTML"
        assert component.disable_web_page_preview is False
        assert component.disable_notification is True

    def test_boolean_string_conversion(self):
        """Test that boolean strings are converted properly."""
        test_cases = [
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("0", False),
            ("no", False),
        ]

        for string_value, expected_bool in test_cases:
            component = DFXTelegramMessageComponent(
                bot_token="test_token",
                chat_id="test_chat",
                message_text="Test",
                disable_web_page_preview=string_value,
                disable_notification=string_value
            )

            assert component.disable_web_page_preview == expected_bool
            assert component.disable_notification == expected_bool

    def test_message_length_validation(self):
        """Test message length validation."""
        # Valid length
        short_message = "Short message"
        component = DFXTelegramMessageComponent(
            bot_token="test_token",
            chat_id="test_chat",
            message_text=short_message
        )
        validation = component._validate_inputs()
        assert validation["valid"]

        # Invalid length (too long)
        long_message = "a" * 4097  # One character over limit
        component = DFXTelegramMessageComponent(
            bot_token="test_token",
            chat_id="test_chat",
            message_text=long_message
        )
        validation = component._validate_inputs()
        assert not validation["valid"]
        assert "exceeds maximum length" in validation["errors"][0]

    def test_required_fields_validation(self):
        """Test required field validation."""
        # Test empty text (only validation that can be tested after __init__)
        component = DFXTelegramMessageComponent(
            bot_token="test_token",
            chat_id="test_chat",
            message_text=""  # Empty text
        )
        validation = component._validate_inputs()
        assert not validation["valid"]
        assert any("text" in error for error in validation["errors"])

        # Test whitespace-only text
        component = DFXTelegramMessageComponent(
            bot_token="test_token",
            chat_id="test_chat",
            message_text="   \n\t   "  # Whitespace only
        )
        validation = component._validate_inputs()
        assert not validation["valid"]

    def test_request_data_preparation(self):
        """Test that component prepares request data correctly."""
        component = DFXTelegramMessageComponent(
            bot_token="  test_token  ",
            chat_id="  test_chat  ",
            message_text="  Test message  ",
            parse_mode="HTML",
            disable_web_page_preview="true",
            disable_notification="false"
        )

        # Test field mapping and boolean conversion
        assert component.bot_token == "  test_token  "  # Stripping happens in send_message
        assert component.chat_id == "  test_chat  "
        assert component.text == "  Test message  "
        assert component.parse_mode == "HTML"
        assert component.disable_web_page_preview is True
        assert component.disable_notification is False

        # Test validation passes
        validation = component._validate_inputs()
        assert validation["valid"]