"""Tests for Telegram message operations."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

from social.telegram.message import (
    SendMessageOperation,
    GetBotInfoOperation,
    TelegramOperations,
    send_message,
    get_bot_info,
    execute_telegram_operation
)
from social.telegram.base import TelegramAPI, TelegramAPIError


class TestSendMessageOperation:
    """Test cases for SendMessageOperation."""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful message sending."""
        mock_api = AsyncMock()
        mock_api._make_request.return_value = {
            "ok": True,
            "result": {"message_id": 123, "chat": {"id": "test_chat"}}
        }

        operation = SendMessageOperation(mock_api)
        payload = {
            "bot_token": "123456:ABC",
            "chat_id": "test_chat",
            "text": "Hello, World!"
        }

        result = await operation.execute(payload)

        assert result["success"] is True
        assert result["message"] == "Message sent successfully"
        assert result["result"]["message_id"] == 123
        mock_api._make_request.assert_called_once_with(
            bot_token="123456:ABC",
            method="sendMessage",
            data={
                "chat_id": "test_chat",
                "text": "Hello, World!"
            }
        )

    @pytest.mark.asyncio
    async def test_execute_with_optional_params(self):
        """Test message sending with optional parameters."""
        mock_api = AsyncMock()
        mock_api._make_request.return_value = {
            "ok": True,
            "result": {"message_id": 123}
        }

        operation = SendMessageOperation(mock_api)
        payload = {
            "bot_token": "123456:ABC",
            "chat_id": "test_chat",
            "text": "Hello, World!",
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
            "disable_notification": False
        }

        result = await operation.execute(payload)

        assert result["success"] is True
        mock_api._make_request.assert_called_once_with(
            bot_token="123456:ABC",
            method="sendMessage",
            data={
                "chat_id": "test_chat",
                "text": "Hello, World!",
                "parse_mode": "Markdown",
                "disable_web_page_preview": True,
                "disable_notification": False
            }
        )

    @pytest.mark.asyncio
    async def test_execute_missing_required_fields(self):
        """Test execution with missing required fields."""
        mock_api = AsyncMock()
        operation = SendMessageOperation(mock_api)

        # Missing bot_token
        payload = {
            "chat_id": "test_chat",
            "text": "Hello, World!"
        }
        result = await operation.execute(payload)
        assert result["success"] is False
        assert "Invalid payload" in result["error"]

        # Missing chat_id
        payload = {
            "bot_token": "123456:ABC",
            "text": "Hello, World!"
        }
        result = await operation.execute(payload)
        assert result["success"] is False
        assert "Invalid payload" in result["error"]

        # Missing text
        payload = {
            "bot_token": "123456:ABC",
            "chat_id": "test_chat"
        }
        result = await operation.execute(payload)
        assert result["success"] is False
        assert "Invalid payload" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_api_error(self):
        """Test handling of Telegram API errors."""
        mock_api = AsyncMock()
        mock_api._make_request.side_effect = TelegramAPIError("Bad Request: chat not found", 400)

        operation = SendMessageOperation(mock_api)
        payload = {
            "bot_token": "123456:ABC",
            "chat_id": "invalid_chat",
            "text": "Hello, World!"
        }

        result = await operation.execute(payload)

        assert result["success"] is False
        assert "Bad Request: chat not found" in result["error"]
        assert result["error_code"] == 400

    @pytest.mark.asyncio
    async def test_execute_unexpected_error(self):
        """Test handling of unexpected errors."""
        mock_api = AsyncMock()
        mock_api._make_request.side_effect = Exception("Unexpected error")

        operation = SendMessageOperation(mock_api)
        payload = {
            "bot_token": "123456:ABC",
            "chat_id": "test_chat",
            "text": "Hello, World!"
        }

        result = await operation.execute(payload)

        assert result["success"] is False
        assert "Unexpected error: Unexpected error" in result["error"]

    def test_validate_payload_valid(self):
        """Test payload validation with valid data."""
        operation = SendMessageOperation(None)
        payload = {
            "bot_token": "123456:ABC",
            "chat_id": "test_chat",
            "text": "Hello, World!"
        }
        assert operation.validate_payload(payload) is True

    def test_validate_payload_invalid(self):
        """Test payload validation with invalid data."""
        operation = SendMessageOperation(None)

        # Missing fields
        payload = {"bot_token": "123456:ABC"}
        assert operation.validate_payload(payload) is False

        # Empty string values
        payload = {
            "bot_token": "",
            "chat_id": "test_chat",
            "text": "Hello, World!"
        }
        assert operation.validate_payload(payload) is False


class TestGetBotInfoOperation:
    """Test cases for GetBotInfoOperation."""

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Test successful bot info retrieval."""
        mock_api = AsyncMock()
        mock_api._make_request.return_value = {
            "ok": True,
            "result": {
                "id": 123456,
                "is_bot": True,
                "first_name": "Test Bot",
                "username": "test_bot"
            }
        }

        operation = GetBotInfoOperation(mock_api)
        payload = {"bot_token": "123456:ABC"}

        result = await operation.execute(payload)

        assert result["success"] is True
        assert result["message"] == "Bot info retrieved successfully"
        assert result["result"]["username"] == "test_bot"
        mock_api._make_request.assert_called_once_with(
            bot_token="123456:ABC",
            method="getMe"
        )

    @pytest.mark.asyncio
    async def test_execute_missing_token(self):
        """Test execution with missing bot token."""
        mock_api = AsyncMock()
        operation = GetBotInfoOperation(mock_api)
        payload = {}

        result = await operation.execute(payload)

        assert result["success"] is False
        assert "Invalid payload" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_api_error(self):
        """Test handling of Telegram API errors."""
        mock_api = AsyncMock()
        mock_api._make_request.side_effect = TelegramAPIError("Unauthorized", 401)

        operation = GetBotInfoOperation(mock_api)
        payload = {"bot_token": "invalid_token"}

        result = await operation.execute(payload)

        assert result["success"] is False
        assert "Unauthorized" in result["error"]
        assert result["error_code"] == 401

    def test_validate_payload_valid(self):
        """Test payload validation with valid token."""
        operation = GetBotInfoOperation(None)
        payload = {"bot_token": "123456:ABC"}
        assert operation.validate_payload(payload) is True

    def test_validate_payload_invalid(self):
        """Test payload validation with invalid token."""
        operation = GetBotInfoOperation(None)
        payload = {}
        assert operation.validate_payload(payload) is False

        payload = {"bot_token": ""}
        assert operation.validate_payload(payload) is False


class TestTelegramOperations:
    """Test cases for TelegramOperations registry."""

    def test_initialization(self):
        """Test operations registry initialization."""
        operations = TelegramOperations()
        assert "send_message" in operations.list_operations()
        assert "get_bot_info" in operations.list_operations()

    def test_register_operation(self):
        """Test registering a new operation."""
        operations = TelegramOperations()

        # Register a new operation
        operations.register_operation("test_operation", SendMessageOperation)
        assert "test_operation" in operations.list_operations()

        # Try to register invalid operation
        with pytest.raises(ValueError):
            operations.register_operation("invalid", str)  # str doesn't inherit from TelegramOperation

    def test_get_operation(self):
        """Test getting operation instances."""
        mock_api = MagicMock()
        operations = TelegramOperations()

        # Get existing operation
        operation = operations.get_operation("send_message", mock_api)
        assert isinstance(operation, SendMessageOperation)
        assert operation.api is mock_api

        # Get non-existent operation
        operation = operations.get_operation("non_existent", mock_api)
        assert operation is None


class TestConvenienceFunctions:
    """Test cases for convenience functions."""

    @pytest.mark.asyncio
    async def test_send_message_function(self):
        """Test send_message convenience function."""
        with patch('social.telegram.message.TelegramAPI') as mock_api_class:
            mock_api_instance = AsyncMock()
            mock_api_class.return_value.__aenter__.return_value = mock_api_instance
            mock_api_instance._make_request.return_value = {
                "ok": True,
                "result": {"message_id": 123}
            }

            payload = {
                "bot_token": "123456:ABC",
                "chat_id": "test_chat",
                "text": "Hello, World!"
            }

            result = await send_message(payload)

            assert result["success"] is True
            mock_api_instance._make_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_bot_info_function(self):
        """Test get_bot_info convenience function."""
        with patch('social.telegram.message.TelegramAPI') as mock_api_class:
            mock_api_instance = AsyncMock()
            mock_api_class.return_value.__aenter__.return_value = mock_api_instance
            mock_api_instance._make_request.return_value = {
                "ok": True,
                "result": {"id": 123, "username": "test_bot"}
            }

            payload = {"bot_token": "123456:ABC"}
            result = await get_bot_info(payload)

            assert result["success"] is True
            mock_api_instance._make_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_telegram_operation_success(self):
        """Test execute_telegram_operation with valid operation."""
        with patch('social.telegram.message.TelegramAPI') as mock_api_class:
            mock_api_instance = AsyncMock()
            mock_api_class.return_value.__aenter__.return_value = mock_api_instance
            mock_api_instance._make_request.return_value = {
                "ok": True,
                "result": {"message_id": 123}
            }

            payload = {
                "bot_token": "123456:ABC",
                "chat_id": "test_chat",
                "text": "Hello, World!"
            }

            result = await execute_telegram_operation("send_message", payload)

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_telegram_operation_unknown(self):
        """Test execute_telegram_operation with unknown operation."""
        payload = {"test": "data"}
        result = await execute_telegram_operation("unknown_operation", payload)

        assert result["success"] is False
        assert "Unknown operation: unknown_operation" in result["error"]
        assert "send_message" in result["available_operations"]
        assert "get_bot_info" in result["available_operations"]