"""Telegram message handlers for DFX social node."""

import logging
from typing import Dict, Any, Optional
from .client import TelegramClient, TelegramMessage, TelegramError, TelegramRateLimitError

logger = logging.getLogger(__name__)


class TelegramMessageHandler:
    """Handles Telegram message operations."""

    def __init__(self, telegram_client: TelegramClient):
        """Initialize Telegram message handler.

        Args:
            telegram_client: Configured Telegram client instance
        """
        self.telegram_client = telegram_client

    async def handle_send_message(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle send message request.

        Args:
            payload: Message request payload containing:
                - bot_token: Telegram bot token
                - chat_id: Target chat ID
                - text: Message text
                - parse_mode: Optional parsing mode (Markdown/HTML)
                - disable_web_page_preview: Optional boolean
                - disable_notification: Optional boolean

        Returns:
            Response dictionary with success status and result or error
        """
        try:
            # Validate required fields
            bot_token = payload.get("bot_token")
            chat_id = payload.get("chat_id")
            text = payload.get("text")

            if not bot_token:
                return self._error_response("bot_token is required")
            if not chat_id:
                return self._error_response("chat_id is required")
            if not text:
                return self._error_response("text is required")

            # Validate bot token format
            if not self.telegram_client.validate_bot_token(bot_token):
                return self._error_response("Invalid bot token format")

            # Create message object
            message = TelegramMessage(
                chat_id=str(chat_id),
                text=text,
                parse_mode=payload.get("parse_mode"),
                disable_web_page_preview=payload.get("disable_web_page_preview"),
                disable_notification=payload.get("disable_notification")
            )

            # Send message
            response = await self.telegram_client.send_message(bot_token, message)

            if response.ok:
                return self._success_response("Message sent successfully", response.result)
            else:
                return self._error_response(
                    response.description or "Unknown error",
                    response.error_code
                )

        except TelegramRateLimitError as e:
            logger.warning(f"Telegram rate limit exceeded: {e}")
            return self._error_response(str(e), e.error_code, retry_after=30)
        except TelegramError as e:
            logger.error(f"Telegram API error: {e}")
            return self._error_response(str(e), e.error_code)
        except Exception as e:
            logger.error(f"Unexpected error in send_message: {e}", exc_info=True)
            return self._error_response(f"Unexpected error: {e}")

    async def handle_get_bot_info(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle get bot info request.

        Args:
            payload: Request payload containing:
                - bot_token: Telegram bot token

        Returns:
            Response dictionary with bot information or error
        """
        try:
            bot_token = payload.get("bot_token")

            if not bot_token:
                return self._error_response("bot_token is required")

            # Validate bot token format
            if not self.telegram_client.validate_bot_token(bot_token):
                return self._error_response("Invalid bot token format")

            response = await self.telegram_client.get_bot_info(bot_token)

            if response.ok:
                return self._success_response("Bot info retrieved", response.result)
            else:
                return self._error_response(
                    response.description or "Unknown error",
                    response.error_code
                )

        except TelegramError as e:
            logger.error(f"Telegram API error: {e}")
            return self._error_response(str(e), e.error_code)
        except Exception as e:
            logger.error(f"Unexpected error in get_bot_info: {e}", exc_info=True)
            return self._error_response(f"Unexpected error: {e}")

    def _success_response(self, message: str, result: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a success response."""
        response = {
            "success": True,
            "message": message
        }
        if result:
            response["result"] = result
        return response

    def _error_response(
        self,
        message: str,
        error_code: Optional[int] = None,
        retry_after: Optional[int] = None
    ) -> Dict[str, Any]:
        """Create an error response."""
        response = {
            "success": False,
            "error": message
        }
        if error_code:
            response["error_code"] = error_code
        if retry_after:
            response["retry_after"] = retry_after
        return response