"""Tests for Telegram client functionality."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import json

from social.telegram.client import (
    TelegramClient,
    TelegramMessage,
    TelegramResponse,
    TelegramError,
    TelegramRateLimitError
)


class TestTelegramClient:
    """Test cases for Telegram client."""

    @pytest.fixture
    def mock_http_client(self):
        """Create a mock HTTP client."""
        return AsyncMock()

    @pytest.fixture
    def telegram_client(self, mock_http_client):
        """Create Telegram client with mock HTTP client."""
        return TelegramClient(mock_http_client)

    @pytest.fixture
    def sample_message(self):
        """Create a sample Telegram message."""
        return TelegramMessage(
            chat_id="123456789",
            text="Hello, World!",
            parse_mode="Markdown"
        )

    @pytest.mark.asyncio
    async def test_send_message_success(self, telegram_client, mock_http_client, sample_message):
        """Test successful message sending."""
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {
                "message_id": 123,
                "chat": {"id": sample_message.chat_id},
                "text": sample_message.text
            }
        }
        mock_http_client.post.return_value = mock_response

        # Send message
        result = await telegram_client.send_message("test_bot_token", sample_message)

        # Verify result
        assert result.ok is True
        assert result.result is not None
        assert result.result["message_id"] == 123
        assert result.result["text"] == sample_message.text

        # Verify HTTP client was called correctly
        mock_http_client.post.assert_called_once()
        call_args = mock_http_client.post.call_args
        assert "sendMessage" in call_args[1]["url"]
        assert call_args[1]["json"]["chat_id"] == sample_message.chat_id
        assert call_args[1]["json"]["text"] == sample_message.text
        assert call_args[1]["json"]["parse_mode"] == sample_message.parse_mode

    @pytest.mark.asyncio
    async def test_send_message_api_error(self, telegram_client, mock_http_client, sample_message):
        """Test handling of API errors."""
        # Mock error response
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": False,
            "error_code": 400,
            "description": "Bad Request: chat not found"
        }
        mock_http_client.post.return_value = mock_response

        # Send message and expect error
        with pytest.raises(TelegramError) as exc_info:
            await telegram_client.send_message("invalid_bot_token", sample_message)

        assert "Bad Request: chat not found" in str(exc_info.value)
        assert exc_info.value.error_code == 400

    @pytest.mark.asyncio
    async def test_send_message_rate_limit_error(self, telegram_client, mock_http_client, sample_message):
        """Test handling of rate limit errors."""
        # Mock rate limit response
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": False,
            "error_code": 429,
            "description": "Too Many Requests: retry after 30 seconds",
            "parameters": {"retry_after": 30}
        }
        mock_http_client.post.return_value = mock_response

        # Send message and expect rate limit error
        with pytest.raises(TelegramRateLimitError) as exc_info:
            await telegram_client.send_message("test_bot_token", sample_message)

        assert "Rate limit exceeded" in str(exc_info.value)
        assert exc_info.value.error_code == 429
        assert "30" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_send_message_timeout_error(self, telegram_client, mock_http_client, sample_message):
        """Test handling of timeout errors."""
        # Mock timeout
        mock_http_client.post.side_effect = asyncio.TimeoutError()

        # Send message and expect error
        with pytest.raises(TelegramError) as exc_info:
            await telegram_client.send_message("test_bot_token", sample_message)

        assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_get_bot_info_success(self, telegram_client, mock_http_client):
        """Test successful bot info retrieval."""
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {
                "id": 123456789,
                "is_bot": True,
                "first_name": "Test Bot",
                "username": "test_bot"
            }
        }
        mock_http_client.get.return_value = mock_response

        # Get bot info
        result = await telegram_client.get_bot_info("test_bot_token")

        # Verify result
        assert result.ok is True
        assert result.result is not None
        assert result.result["username"] == "test_bot"
        assert result.result["first_name"] == "Test Bot"

        # Verify HTTP client was called correctly
        mock_http_client.get.assert_called_once()
        call_args = mock_http_client.get.call_args
        assert "getMe" in call_args[1]["url"]

    @pytest.mark.asyncio
    async def test_get_bot_info_error(self, telegram_client, mock_http_client):
        """Test handling of bot info errors."""
        # Mock error response
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": False,
            "error_code": 401,
            "description": "Unauthorized"
        }
        mock_http_client.get.return_value = mock_response

        # Get bot info and expect error
        with pytest.raises(TelegramError) as exc_info:
            await telegram_client.get_bot_info("invalid_bot_token")

        assert "Unauthorized" in str(exc_info.value)
        assert exc_info.value.error_code == 401

    def test_validate_bot_token_valid(self, telegram_client):
        """Test valid bot token validation."""
        valid_tokens = [
            "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
            "1:token",
            "999999999:abcdefghijklmnopqrstuvwxyz123456"
        ]

        for token in valid_tokens:
            assert telegram_client.validate_bot_token(token) is True

    def test_validate_bot_token_invalid(self, telegram_client):
        """Test invalid bot token validation."""
        invalid_tokens = [
            "",  # Empty
            "123456789",  # Missing colon and token
            "token",  # Missing ID and colon
            "abc:token",  # Non-numeric ID
            "123456789:short",  # Token too short
            "123456789:",  # Empty token
            ":token",  # Empty ID
            "123456789:token:extra",  # Too many colons
            None  # None value
        ]

        for token in invalid_tokens:
            assert telegram_client.validate_bot_token(token) is False

    @pytest.mark.asyncio
    async def test_rate_limiting(self, telegram_client, mock_http_client, sample_message):
        """Test rate limiting functionality."""
        # Mock successful response
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 123}
        }
        mock_http_client.post.return_value = mock_response

        # Send multiple messages rapidly
        start_time = asyncio.get_event_loop().time()
        tasks = []
        for _ in range(3):
            task = telegram_client.send_message("test_bot_token", sample_message)
            tasks.append(task)

        # Wait for all tasks to complete
        await asyncio.gather(*tasks)
        end_time = asyncio.get_event_loop().time()

        # Verify that rate limiting added delay (should take at least 2 * min_interval for 3 messages)
        elapsed_time = end_time - start_time
        expected_min_time = 2 * telegram_client._min_request_interval
        assert elapsed_time >= expected_min_time

        # Verify all requests were made
        assert mock_http_client.post.call_count == 3