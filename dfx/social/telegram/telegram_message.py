"""Telegram message component for sending messages via Telegram Bot API."""

import aiohttp
import asyncio
from typing import Any, Dict, Optional

from dfx import Component, Data, StrInput, Output


class TelegramAPIError(Exception):
    """Custom exception for Telegram API errors."""

    def __init__(self, message: str, error_code: Optional[int] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class TelegramHTTPError(Exception):
    """Custom exception for Telegram HTTP errors."""

    def __init__(self, message: str, error_code: Optional[int] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(message)


class TelegramAPI:
    """Telegram API client for making requests to the Bot API."""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            self.session = None

    def _get_endpoint_url(self, bot_token: str, method: str) -> str:
        """Get the full endpoint URL for a Telegram API method."""
        return f"https://api.telegram.org/bot{bot_token}/{method}"

    async def _make_request(
        self,
        bot_token: str,
        method: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a request to the Telegram API."""
        if not self.session:
            self.session = aiohttp.ClientSession()

        url = self._get_endpoint_url(bot_token, method)

        try:
            if data:
                # POST request for methods with data
                async with self.session.post(url, json=data) as response:
                    result = await response.json()

                    if not result.get("ok", False):
                        raise TelegramAPIError(
                            result.get("description", "Unknown API error"),
                            result.get("error_code")
                        )

                    return result
            else:
                # GET request for methods without data
                async with self.session.get(url) as response:
                    result = await response.json()

                    if not result.get("ok", False):
                        raise TelegramAPIError(
                            result.get("description", "Unknown API error"),
                            result.get("error_code")
                        )

                    return result

        except aiohttp.ClientError as e:
            raise TelegramHTTPError(f"HTTP error: {str(e)}")


class DFXTelegramMessageComponent(Component):
    """Component for sending messages via Telegram Bot API.

    This component allows sending text messages to Telegram chats using
    the Bot API. It supports various formatting options and message
    configurations.
    """

    display_name: str = "DFX Telegram Message"
    description: str = "Send messages to Telegram chats via Bot API"
    icon: str = "message-circle"
    name: str = "DFXTelegramMessage"

    inputs: list = [
        StrInput(
            name="bot_token",
            display_name="Bot Token",
            info="Telegram bot token (get from @BotFather)",
            value="",
            required=True
        ),
        StrInput(
            name="chat_id",
            display_name="Chat ID",
            info="Target chat ID (can be user ID, group ID, or channel username)",
            value="",
            required=True
        ),
        StrInput(
            name="text",
            display_name="Message Text",
            info="Text message to send (max 4096 characters)",
            value="",
            required=True
        ),
        StrInput(
            name="parse_mode",
            display_name="Parse Mode",
            info="Text formatting: 'Markdown', 'MarkdownV2', or 'HTML'",
            value="",
            required=False
        ),
        StrInput(
            name="disable_web_page_preview",
            display_name="Disable Web Preview",
            info="Disable link previews in the message (True/False)",
            value="False",
            required=False
        ),
        StrInput(
            name="disable_notification",
            display_name="Silent Message",
            info="Send message silently (True/False)",
            value="False",
            required=False
        )
    ]

    outputs: list = [
        Output(
            display_name="Message Result",
            name="result",
            type_=Data,
            method="send_message",
        )
    ]

    def __init__(self, **kwargs):
        """Initialize component with parameter mapping for compatibility."""
        # Map application parameter names to component parameter names
        param_mapping = {
            'message_text': 'text',
            'disable_preview': 'disable_web_page_preview',
            'silent': 'disable_notification'
        }

        # Apply parameter mapping
        mapped_kwargs = {}
        for key, value in kwargs.items():
            if key in param_mapping:
                mapped_kwargs[param_mapping[key]] = value
            else:
                mapped_kwargs[key] = value

        # Handle boolean conversion for strings
        for bool_field in ['disable_web_page_preview', 'disable_notification']:
            if bool_field in mapped_kwargs:
                val = mapped_kwargs[bool_field]
                if isinstance(val, bool):
                    continue
                if isinstance(val, str):
                    mapped_kwargs[bool_field] = val.lower() in ['true', '1', 'yes']
                else:
                    mapped_kwargs[bool_field] = bool(val)

        # Parse mode handling - convert "None" to empty string
        if 'parse_mode' in mapped_kwargs and mapped_kwargs['parse_mode'] == 'None':
            mapped_kwargs['parse_mode'] = ''

        super().__init__(**mapped_kwargs)

    def _validate_inputs(self) -> Dict[str, Any]:
        """Validate required inputs and return parsed data."""
        errors = []

        # Check required fields
        if not self.bot_token or not self.bot_token.strip():
            errors.append("bot_token is required")

        if not self.chat_id or not self.chat_id.strip():
            errors.append("chat_id is required")

        if not self.text or not self.text.strip():
            errors.append("text is required")

        # Check text length
        if self.text and len(self.text) > 4096:
            errors.append("text exceeds maximum length of 4096 characters")

        # Validate parse_mode - Telegram API supports: Markdown, MarkdownV2, HTML
        if self.parse_mode and self.parse_mode not in ["Markdown", "MarkdownV2", "HTML", ""]:
            errors.append("parse_mode must be 'Markdown', 'MarkdownV2', 'HTML', or empty")

        # Validate boolean fields (already converted to bool in __init__)
        # No validation needed since conversion happens in __init__

        if errors:
            return {"valid": False, "errors": errors}

        return {"valid": True}

    def _parse_boolean(self, value: str) -> bool:
        """Parse string value to boolean."""
        if not value:
            return False
        return value.lower() in ["true", "1", "yes"]

    async def send_message(self) -> Data:
        """Send a message via Telegram Bot API.

        Returns:
            Data: Contains the result of the message sending operation.
        """
        try:
            # Validate inputs
            validation = self._validate_inputs()
            if not validation["valid"]:
                error_message = "Validation failed: " + "; ".join(validation["errors"])
                self.status = error_message
                self.log(error_message)
                return Data(
                    data={
                        "success": False,
                        "error": error_message,
                        "operation": "send_message"
                    }
                )

            # Prepare request data
            request_data = {
                "chat_id": self.chat_id.strip(),
                "text": self.text.strip()
            }

            # Add optional parameters
            if self.parse_mode:
                request_data["parse_mode"] = self.parse_mode

            if self._parse_boolean(self.disable_web_page_preview):
                request_data["disable_web_page_preview"] = True

            if self._parse_boolean(self.disable_notification):
                request_data["disable_notification"] = True

            # Log the operation
            self.log(f"Sending Telegram message to chat {self.chat_id}")

            # Make API request
            async with TelegramAPI() as api:
                response = await api._make_request(
                    bot_token=self.bot_token.strip(),
                    method="sendMessage",
                    data=request_data
                )

            # Extract message info
            message_info = response.get("result", {})
            message_id = message_info.get("message_id")
            chat_info = message_info.get("chat", {})

            # Log success
            success_msg = f"Message sent successfully (ID: {message_id})"
            self.status = success_msg
            self.log(success_msg)

            # Return success result
            return Data(
                data={
                    "success": True,
                    "message": "Message sent successfully",
                    "message_id": message_id,
                    "chat_id": self.chat_id.strip(),
                    "chat_info": chat_info,
                    "text": self.text.strip(),
                    "operation": "send_message",
                    "api_response": response
                }
            )

        except TelegramAPIError as e:
            error_message = f"Telegram API error: {e.message}"
            self.status = error_message
            self.log(error_message)
            return Data(
                data={
                    "success": False,
                    "error": error_message,
                    "error_code": e.error_code,
                    "error_type": "api_error",
                    "operation": "send_message"
                }
            )

        except TelegramHTTPError as e:
            error_message = f"HTTP error: {e.message}"
            self.status = error_message
            self.log(error_message)
            return Data(
                data={
                    "success": False,
                    "error": error_message,
                    "error_type": "http_error",
                    "operation": "send_message"
                }
            )

        except Exception as e:
            error_message = f"Unexpected error: {str(e)}"
            self.status = error_message
            self.log(error_message)
            return Data(
                data={
                    "success": False,
                    "error": error_message,
                    "error_type": "unexpected_error",
                    "operation": "send_message"
                }
            )

    def build(self):
        """Return the main send_message function."""
        return self.send_message