"""Tests for Telegram base classes."""

import pytest
from unittest.mock import AsyncMock, MagicMock
import aiohttp

from dfx.social.telegram.telegram_message import TelegramAPI, TelegramAPIError, TelegramHTTPError


class TestTelegramAPI:
    """Test cases for TelegramAPI."""

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager functionality."""
        async with TelegramAPI() as api:
            assert api.session is not None
            assert isinstance(api.session, aiohttp.ClientSession)
        # Session should be closed after context exit

    @pytest.mark.asyncio
    async def test_get_endpoint_url(self):
        """Test endpoint URL generation."""
        api = TelegramAPI()
        url = api._get_endpoint_url("123456:ABC", "sendMessage")
        expected = "https://api.telegram.org/bot123456:ABC/sendMessage"
        assert url == expected

    @pytest.mark.asyncio
    async def test_make_request_success_post(self):
        """Test successful POST request."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"message_id": 123}
        }

        # Create a proper async context manager mock
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post.return_value = mock_context

        api = TelegramAPI()
        api.session = mock_session

        result = await api._make_request(
            bot_token="123456:ABC",
            method="sendMessage",
            data={"chat_id": "123", "text": "Hello"}
        )

        assert result["ok"] is True
        assert result["result"]["message_id"] == 123
        mock_session.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_success_get(self):
        """Test successful GET request."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {"id": 123, "username": "test_bot"}
        }

        # Create a proper async context manager mock
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_context

        api = TelegramAPI()
        api.session = mock_session

        result = await api._make_request(
            bot_token="123456:ABC",
            method="getMe"
        )

        assert result["ok"] is True
        assert result["result"]["id"] == 123
        mock_session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_make_request_api_error(self):
        """Test API error response."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {
            "ok": False,
            "error_code": 400,
            "description": "Bad Request: chat not found"
        }

        # Create a proper async context manager mock
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post.return_value = mock_context

        api = TelegramAPI()
        api.session = mock_session

        with pytest.raises(TelegramAPIError) as exc_info:
            await api._make_request(
                bot_token="123456:ABC",
                method="sendMessage",
                data={"chat_id": "invalid", "text": "Hello"}
            )

        assert "Bad Request: chat not found" in str(exc_info.value)
        assert exc_info.value.error_code == 400

    @pytest.mark.asyncio
    async def test_make_request_http_error(self):
        """Test HTTP client error."""
        mock_session = AsyncMock()
        mock_session.post.side_effect = aiohttp.ClientError("Connection failed")

        api = TelegramAPI()
        api.session = mock_session

        with pytest.raises(TelegramHTTPError) as exc_info:
            await api._make_request(
                bot_token="123456:ABC",
                method="sendMessage",
                data={"chat_id": "123", "text": "Hello"}
            )

        assert "HTTP error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_make_request_session_creation(self):
        """Test session creation if not exists."""
        mock_response = AsyncMock()
        mock_response.json.return_value = {"ok": True}

        # Create a proper async context manager mock
        mock_context = AsyncMock()
        mock_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_context.__aexit__ = AsyncMock(return_value=None)

        mock_session = AsyncMock()
        mock_session.post.return_value = mock_context

        with pytest.MonkeyPatch().context() as m:
            m.setattr("aiohttp.ClientSession", lambda: mock_session)

            api = TelegramAPI()
            # Don't set session manually

            result = await api._make_request(
                bot_token="123456:ABC",
                method="sendMessage",
                data={"chat_id": "123", "text": "Hello"}
            )

            assert result["ok"] is True
            assert api.session is mock_session

    def test_base_error_creation(self):
        """Test TelegramAPIError creation."""
        error = TelegramAPIError("Test error", 400)
        assert str(error) == "Test error"
        assert error.error_code == 400

    def test_http_error_creation(self):
        """Test TelegramHTTPError creation."""
        error = TelegramHTTPError("Connection failed")
        assert str(error) == "Connection failed"
        assert error.error_code is None