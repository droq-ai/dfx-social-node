"""Telegram Bot API client for DFX social node."""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import json

from node.http import HTTPClient
from node.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TelegramMessage:
    """Telegram message data structure."""
    chat_id: str
    text: str
    parse_mode: Optional[str] = None  # 'Markdown' or 'HTML'
    disable_web_page_preview: Optional[bool] = None
    disable_notification: Optional[bool] = None


@dataclass
class TelegramResponse:
    """Telegram API response structure."""
    ok: bool
    result: Optional[Dict[str, Any]] = None
    error_code: Optional[int] = None
    description: Optional[str] = None


class TelegramError(Exception):
    """Base exception for Telegram API errors."""

    def __init__(self, message: str, error_code: Optional[int] = None):
        super().__init__(message)
        self.error_code = error_code


class TelegramRateLimitError(TelegramError):
    """Raised when Telegram API rate limit is exceeded."""
    pass


class TelegramClient:
    """Telegram Bot API client with error handling and rate limiting."""

    def __init__(self, http_client: HTTPClient):
        """Initialize Telegram client.

        Args:
            http_client: HTTP client instance for making API requests
        """
        self.http_client = http_client
        self.base_url = "https://api.telegram.org/bot"
        self._rate_limit_lock = asyncio.Lock()
        self._last_request_time = 0
        self._min_request_interval = 0.034  # ~30 requests per second

    async def send_message(self, bot_token: str, message: TelegramMessage) -> TelegramResponse:
        """Send a message via Telegram Bot API.

        Args:
            bot_token: Telegram bot token
            message: Message to send

        Returns:
            TelegramResponse with API response data

        Raises:
            TelegramError: If API request fails
            TelegramRateLimitError: If rate limit is exceeded
        """
        await self._enforce_rate_limit()

        url = f"{self.base_url}{bot_token}/sendMessage"
        payload = {
            "chat_id": message.chat_id,
            "text": message.text
        }

        # Add optional parameters
        if message.parse_mode:
            payload["parse_mode"] = message.parse_mode
        if message.disable_web_page_preview is not None:
            payload["disable_web_page_preview"] = message.disable_web_page_preview
        if message.disable_notification is not None:
            payload["disable_notification"] = message.disable_notification

        try:
            logger.debug(f"Sending Telegram message to chat_id: {message.chat_id}")

            response = await self.http_client.post(
                url=url,
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            response_data = await response.json()

            if response_data.get("ok"):
                logger.info(f"Telegram message sent successfully to chat_id: {message.chat_id}")
                return TelegramResponse(
                    ok=True,
                    result=response_data.get("result")
                )
            else:
                error_code = response_data.get("error_code")
                description = response_data.get("description", "Unknown error")

                # Handle rate limit errors specifically
                if error_code == 429:
                    retry_after = response_data.get("parameters", {}).get("retry_after", 1)
                    logger.warning(f"Telegram rate limit exceeded, retry after {retry_after}s")
                    raise TelegramRateLimitError(
                        f"Rate limit exceeded. Retry after {retry_after} seconds",
                        error_code=error_code
                    )

                logger.error(f"Telegram API error: {description} (code: {error_code})")
                raise TelegramError(
                    f"Telegram API error: {description}",
                    error_code=error_code
                )

        except asyncio.TimeoutError:
            logger.error("Telegram API request timed out")
            raise TelegramError("Telegram API request timed out")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode Telegram API response: {e}")
            raise TelegramError(f"Invalid JSON response from Telegram API: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in Telegram API request: {e}")
            raise TelegramError(f"Unexpected error: {e}")

    async def get_bot_info(self, bot_token: str) -> TelegramResponse:
        """Get bot information using the provided token.

        Args:
            bot_token: Telegram bot token

        Returns:
            TelegramResponse with bot information

        Raises:
            TelegramError: If API request fails
        """
        await self._enforce_rate_limit()

        url = f"{self.base_url}{bot_token}/getMe"

        try:
            logger.debug("Getting Telegram bot info")

            response = await self.http_client.get(url)
            response_data = await response.json()

            if response_data.get("ok"):
                logger.info("Successfully retrieved Telegram bot info")
                return TelegramResponse(
                    ok=True,
                    result=response_data.get("result")
                )
            else:
                error_code = response_data.get("error_code")
                description = response_data.get("description", "Unknown error")

                logger.error(f"Failed to get bot info: {description} (code: {error_code})")
                raise TelegramError(
                    f"Failed to get bot info: {description}",
                    error_code=error_code
                )

        except Exception as e:
            logger.error(f"Error getting bot info: {e}")
            raise TelegramError(f"Error getting bot info: {e}")

    async def _enforce_rate_limit(self):
        """Enforce minimum interval between requests to respect rate limits."""
        async with self._rate_limit_lock:
            current_time = asyncio.get_event_loop().time()
            elapsed = current_time - self._last_request_time

            if elapsed < self._min_request_interval:
                wait_time = self._min_request_interval - elapsed
                logger.debug(f"Rate limiting: waiting {wait_time:.3f}s")
                await asyncio.sleep(wait_time)

            self._last_request_time = asyncio.get_event_loop().time()

    def validate_bot_token(self, bot_token: str) -> bool:
        """Validate Telegram bot token format.

        Args:
            bot_token: Bot token to validate

        Returns:
            True if token format is valid, False otherwise
        """
        # Basic token format validation: numbers:string
        if not bot_token or ':' not in bot_token:
            return False

        try:
            parts = bot_token.split(':')
            if len(parts) != 2:
                return False

            # First part should be numbers (bot ID)
            int(parts[0])
            # Second part should be the token string
            if len(parts[1]) < 10:  # Tokens are typically longer
                return False

            return True
        except (ValueError, IndexError):
            return False