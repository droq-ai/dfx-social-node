"""Tests for Telegram message handler functionality."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from social.telegram.client import TelegramMessage, TelegramError, TelegramRateLimitError
from social.telegram.handler import TelegramMessageHandler


class TestTelegramMessageHandler:
    """Test cases for Telegram message handler."""

    @pytest.fixture
    def mock_telegram_client(self):
        """Create a mock Telegram client."""
        return AsyncMock()

    @pytest.fixture
    def telegram_handler(self, mock_telegram_client):
        """Create Telegram message handler with mock client."""
        return TelegramMessageHandler(mock_telegram_client)

    @pytest.mark.asyncio
    async def test_handle_send_message_success(self, telegram_handler, mock_telegram_client):
        """Test successful send message handling."""
        # Mock successful Telegram client response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.result = {"message_id": 123, "chat_id": "123456789"}
        mock_telegram_client.send_message.return_value = mock_response
        mock_telegram_client.validate_bot_token.return_value = True

        # Test payload
        payload = {
            "bot_token": "123456789:valid_token",
            "chat_id": "123456789",
            "text": "Hello, World!",
            "parse_mode": "Markdown"
        }

        # Handle message
        result = await telegram_handler.handle_send_message(payload)

        # Verify result
        assert result["success"] is True
        assert "Message sent successfully" in result["message"]
        assert result["result"]["message_id"] == 123

        # Verify Telegram client was called correctly
        mock_telegram_client.validate_bot_token.assert_called_once_with("123456789:valid_token")
        mock_telegram_client.send_message.assert_called_once()
        call_args = mock_telegram_client.send_message.call_args[0][0]
        assert isinstance(call_args, TelegramMessage)
        assert call_args.chat_id == "123456789"
        assert call_args.text == "Hello, World!"
        assert call_args.parse_mode == "Markdown"

    @pytest.mark.asyncio
    async def test_handle_send_message_missing_fields(self, telegram_handler):
        """Test send message handling with missing required fields."""
        # Test with missing bot_token
        payload = {"chat_id": "123456789", "text": "Hello"}
        result = await telegram_handler.handle_send_message(payload)
        assert result["success"] is False
        assert "bot_token is required" in result["error"]

        # Test with missing chat_id
        payload = {"bot_token": "123456789:token", "text": "Hello"}
        result = await telegram_handler.handle_send_message(payload)
        assert result["success"] is False
        assert "chat_id is required" in result["error"]

        # Test with missing text
        payload = {"bot_token": "123456789:token", "chat_id": "123456789"}
        result = await telegram_handler.handle_send_message(payload)
        assert result["success"] is False
        assert "text is required" in result["error"]

    @pytest.mark.asyncio
    async def test_handle_send_message_invalid_token(self, telegram_handler, mock_telegram_client):
        """Test send message handling with invalid token format."""
        mock_telegram_client.validate_bot_token.return_value = False

        payload = {
            "bot_token": "invalid_token",
            "chat_id": "123456789",
            "text": "Hello"
        }

        result = await telegram_handler.handle_send_message(payload)

        assert result["success"] is False
        assert "Invalid bot token format" in result["error"]
        mock_telegram_client.validate_bot_token.assert_called_once_with("invalid_token")

    @pytest.mark.asyncio
    async def test_handle_send_message_rate_limit_error(self, telegram_handler, mock_telegram_client):
        """Test send message handling with rate limit error."""
        mock_telegram_client.validate_bot_token.return_value = True
        mock_telegram_client.send_message.side_effect = TelegramRateLimitError(
            "Rate limit exceeded. Retry after 30 seconds",
            error_code=429
        )

        payload = {
            "bot_token": "123456789:valid_token",
            "chat_id": "123456789",
            "text": "Hello"
        }

        result = await telegram_handler.handle_send_message(payload)

        assert result["success"] is False
        assert "Rate limit exceeded" in result["error"]
        assert result["error_code"] == 429
        assert result["retry_after"] == 30

    @pytest.mark.asyncio
    async def test_handle_send_message_telegram_error(self, telegram_handler, mock_telegram_client):
        """Test send message handling with Telegram API error."""
        mock_telegram_client.validate_bot_token.return_value = True
        mock_telegram_client.send_message.side_effect = TelegramError(
            "Bad Request: chat not found",
            error_code=400
        )

        payload = {
            "bot_token": "123456789:valid_token",
            "chat_id": "invalid_chat",
            "text": "Hello"
        }

        result = await telegram_handler.handle_send_message(payload)

        assert result["success"] is False
        assert "Bad Request: chat not found" in result["error"]
        assert result["error_code"] == 400

    @pytest.mark.asyncio
    async def test_handle_send_message_unexpected_error(self, telegram_handler, mock_telegram_client):
        """Test send message handling with unexpected error."""
        mock_telegram_client.validate_bot_token.return_value = True
        mock_telegram_client.send_message.side_effect = Exception("Unexpected error")

        payload = {
            "bot_token": "123456789:valid_token",
            "chat_id": "123456789",
            "text": "Hello"
        }

        result = await telegram_handler.handle_send_message(payload)

        assert result["success"] is False
        assert "Unexpected error" in result["error"]

    @pytest.mark.asyncio
    async def test_handle_get_bot_info_success(self, telegram_handler, mock_telegram_client):
        """Test successful get bot info handling."""
        # Mock successful Telegram client response
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.result = {
            "id": 123456789,
            "is_bot": True,
            "first_name": "Test Bot",
            "username": "test_bot"
        }
        mock_telegram_client.get_bot_info.return_value = mock_response
        mock_telegram_client.validate_bot_token.return_value = True

        # Test payload
        payload = {"bot_token": "123456789:valid_token"}

        # Handle request
        result = await telegram_handler.handle_get_bot_info(payload)

        # Verify result
        assert result["success"] is True
        assert "Bot info retrieved" in result["message"]
        assert result["result"]["username"] == "test_bot"

        # Verify Telegram client was called correctly
        mock_telegram_client.validate_bot_token.assert_called_once_with("123456789:valid_token")
        mock_telegram_client.get_bot_info.assert_called_once_with("123456789:valid_token")

    @pytest.mark.asyncio
    async def test_handle_get_bot_info_missing_token(self, telegram_handler):
        """Test get bot info handling with missing bot token."""
        payload = {}

        result = await telegram_handler.handle_get_bot_info(payload)

        assert result["success"] is False
        assert "bot_token is required" in result["error"]

    @pytest.mark.asyncio
    async def test_handle_get_bot_info_invalid_token(self, telegram_handler, mock_telegram_client):
        """Test get bot info handling with invalid token format."""
        mock_telegram_client.validate_bot_token.return_value = False

        payload = {"bot_token": "invalid_token"}

        result = await telegram_handler.handle_get_bot_info(payload)

        assert result["success"] is False
        assert "Invalid bot token format" in result["error"]

    @pytest.mark.asyncio
    async def test_handle_get_bot_info_api_error(self, telegram_handler, mock_telegram_client):
        """Test get bot info handling with API error."""
        mock_telegram_client.validate_bot_token.return_value = True
        mock_telegram_client.get_bot_info.side_effect = TelegramError(
            "Unauthorized",
            error_code=401
        )

        payload = {"bot_token": "invalid_token"}

        result = await telegram_handler.handle_get_bot_info(payload)

        assert result["success"] is False
        assert "Unauthorized" in result["error"]
        assert result["error_code"] == 401

    @pytest.mark.asyncio
    async def test_handle_send_message_optional_fields(self, telegram_handler, mock_telegram_client):
        """Test send message handling with optional fields."""
        mock_response = MagicMock()
        mock_response.ok = True
        mock_response.result = {"message_id": 123}
        mock_telegram_client.send_message.return_value = mock_response
        mock_telegram_client.validate_bot_token.return_value = True

        # Test payload with all optional fields
        payload = {
            "bot_token": "123456789:valid_token",
            "chat_id": "123456789",
            "text": "Hello with options",
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "disable_notification": False
        }

        result = await telegram_handler.handle_send_message(payload)

        assert result["success"] is True

        # Verify Telegram client was called with all optional fields
        call_args = mock_telegram_client.send_message.call_args[0][0]
        assert call_args.parse_mode == "HTML"
        assert call_args.disable_web_page_preview is True
        assert call_args.disable_notification is False

    def test_success_response_creation(self, telegram_handler):
        """Test success response creation."""
        result = telegram_handler._success_response("Test message")
        assert result["success"] is True
        assert result["message"] == "Test message"
        assert "result" not in result

        result = telegram_handler._success_response("Test message", {"key": "value"})
        assert result["success"] is True
        assert result["message"] == "Test message"
        assert result["result"]["key"] == "value"

    def test_error_response_creation(self, telegram_handler):
        """Test error response creation."""
        result = telegram_handler._error_response("Test error")
        assert result["success"] is False
        assert result["error"] == "Test error"
        assert "error_code" not in result
        assert "retry_after" not in result

        result = telegram_handler._error_response("Test error", error_code=400, retry_after=30)
        assert result["success"] is False
        assert result["error"] == "Test error"
        assert result["error_code"] == 400
        assert result["retry_after"] == 30