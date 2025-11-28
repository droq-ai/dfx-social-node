"""Simple Telegram message component for DFX social node."""

import asyncio
import logging
from typing import Dict, Any, Optional

import aiohttp

logger = logging.getLogger(__name__)


async def send_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Send a message to Telegram chat via Bot API.

    Args:
        payload: Dictionary containing:
            - bot_token (str): Telegram bot token (required)
            - chat_id (str): Target chat ID (required)
            - text (str): Message text (required)
            - parse_mode (str, optional): 'Markdown' or 'HTML'
            - disable_web_page_preview (bool, optional): Disable link preview
            - disable_notification (bool, optional): Send silently

    Returns:
        Dictionary with success status and response data
    """
    try:
        # Validate required fields
        bot_token = payload.get("bot_token")
        chat_id = payload.get("chat_id")
        text = payload.get("text")

        if not all([bot_token, chat_id, text]):
            return {
                "success": False,
                "error": "Missing required fields: bot_token, chat_id, text"
            }

        # Build request URL
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        # Build request payload
        request_data = {
            "chat_id": str(chat_id),
            "text": text
        }

        # Add optional parameters
        if payload.get("parse_mode"):
            request_data["parse_mode"] = payload["parse_mode"]
        if payload.get("disable_web_page_preview") is not None:
            request_data["disable_web_page_preview"] = payload["disable_web_page_preview"]
        if payload.get("disable_notification") is not None:
            request_data["disable_notification"] = payload["disable_notification"]

        # Make HTTP request
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=request_data) as response:
                response_data = await response.json()

                if response_data.get("ok"):
                    logger.info(f"Message sent successfully to chat_id: {chat_id}")
                    return {
                        "success": True,
                        "result": response_data.get("result"),
                        "message": "Message sent successfully"
                    }
                else:
                    error_code = response_data.get("error_code")
                    description = response_data.get("description", "Unknown error")
                    logger.error(f"Telegram API error: {description} (code: {error_code})")
                    return {
                        "success": False,
                        "error": description,
                        "error_code": error_code
                    }

    except aiohttp.ClientError as e:
        logger.error(f"HTTP error sending Telegram message: {e}")
        return {
            "success": False,
            "error": f"HTTP error: {e}"
        }
    except Exception as e:
        logger.error(f"Unexpected error sending Telegram message: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {e}"
        }


async def get_bot_info(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get bot information using the provided token.

    Args:
        payload: Dictionary containing:
            - bot_token (str): Telegram bot token (required)

    Returns:
        Dictionary with success status and bot information
    """
    try:
        bot_token = payload.get("bot_token")

        if not bot_token:
            return {
                "success": False,
                "error": "Missing required field: bot_token"
            }

        # Build request URL
        url = f"https://api.telegram.org/bot{bot_token}/getMe"

        # Make HTTP request
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response_data = await response.json()

                if response_data.get("ok"):
                    logger.info("Bot info retrieved successfully")
                    return {
                        "success": True,
                        "result": response_data.get("result"),
                        "message": "Bot info retrieved successfully"
                    }
                else:
                    error_code = response_data.get("error_code")
                    description = response_data.get("description", "Unknown error")
                    logger.error(f"Telegram API error: {description} (code: {error_code})")
                    return {
                        "success": False,
                        "error": description,
                        "error_code": error_code
                    }

    except aiohttp.ClientError as e:
        logger.error(f"HTTP error getting bot info: {e}")
        return {
            "success": False,
            "error": f"HTTP error: {e}"
        }
    except Exception as e:
        logger.error(f"Unexpected error getting bot info: {e}")
        return {
            "success": False,
            "error": f"Unexpected error: {e}"
        }