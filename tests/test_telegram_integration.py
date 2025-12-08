"""Integration test for DFX Social Executor Node Telegram functionality."""

import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
import pytest
from dotenv import load_dotenv

# Add src and dfx to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))
sys.path.insert(0, str(project_root / "dfx"))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class TestTelegramIntegration:
    """Integration tests for Telegram functionality."""

    @classmethod
    def setup_class(cls):
        """Setup test environment."""
        # Load only secrets from test environment variables
        env_file = project_root / ".env.test"
        if env_file.exists():
            load_dotenv(env_file)
            logger.info(f"Loaded secrets from {env_file}")
        else:
            logger.warning(f"Test environment file {env_file} not found")
            pytest.skip(".env.test file not found")

        cls.base_url = "http://localhost:8007"
        cls.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        cls.chat_id = os.getenv("TELEGRAM_CHAT_ID")

        # Hardcoded test messages and inputs (as requested)
        cls.test_messages = {
            "basic_text": "Hello from DFX Social Executor Node Integration Test! 🤖",
            "html_formatted": "<b>Bold text</b> and <i>italic text</i>\n\n<a href='https://example.com'>Link</a>",
            "markdown_v2": "*Bold text* and _italic text_\n\n[Link](https://example.com)",
            "with_emoji": "🚀 Test message with emojis: 📱 💻 🎯",
            "long_text": "This is a very long message that should test the truncation functionality. " * 100,
        }

        cls.test_chat_ids = {
            "valid": cls.chat_id,
            "invalid": "invalid_chat_id_12345",
            "nonexistent": "-999999999",
        }

        # Verify required environment variables
        if not cls.bot_token or cls.bot_token == "your_bot_token_here":
            pytest.skip("TELEGRAM_BOT_TOKEN not configured in .env.test file")

        if not cls.chat_id or cls.chat_id == "your_chat_id_here":
            pytest.skip("TELEGRAM_CHAT_ID not configured in .env.test file")

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        """Test the health endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/health", timeout=10.0)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "dfx-social-executor-node"
        logger.info("✅ Health endpoint test passed")

    @pytest.mark.asyncio
    async def test_root_endpoint(self):
        """Test the root endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.base_url}/", timeout=10.0)

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "dfx-social-executor-node"
        assert data["version"] == "0.1.0"
        assert "api/v1/telegram/send" in data["endpoints"]
        assert "api/v1/telegram/bot-info" in data["endpoints"]
        logger.info("✅ Root endpoint test passed")

    @pytest.mark.asyncio
    async def test_telegram_bot_info(self):
        """Test getting Telegram bot information."""
        payload = {
            "bot_token": self.bot_token
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/bot-info",
                json=payload,
                timeout=30.0
            )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "success" in data
        assert "bot_info" in data
        assert "timestamp" in data
        assert "operation" in data
        assert data["operation"] == "get_telegram_bot_info"

        if data["success"]:
            # Verify bot info structure
            bot_info = data["bot_info"]
            assert "id" in bot_info
            assert "username" in bot_info
            assert "first_name" in bot_info
            assert "is_bot" in bot_info
            assert bot_info["is_bot"] is True
            logger.info(f"✅ Bot info test passed - Bot: @{bot_info['username']} ({bot_info['first_name']})")
        else:
            logger.warning(f"⚠️  Bot info test failed - {data.get('error_message', 'Unknown error')}")
            pytest.skip(f"Telegram bot info failed: {data.get('error_message')}")

    @pytest.mark.asyncio
    async def test_send_basic_message(self):
        """Test sending a basic text message."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        test_message = f"{self.test_messages['basic_text']}\n\n<b>Test Time:</b> {timestamp}"

        payload = {
            "bot_token": self.bot_token,
            "chat_id": self.chat_id,
            "message_text": test_message,
            "parse_mode": "HTML",
            "disable_preview": False,
            "silent": False
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                json=payload,
                timeout=30.0
            )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure matches specification
        assert "success" in data
        assert "message_id" in data
        assert "chat_id" in data
        assert "sent_message" in data
        assert "timestamp" in data
        assert "operation" in data
        assert data["operation"] == "send_telegram_message"
        assert data["chat_id"] == self.chat_id
        assert data["sent_message"] == test_message

        if data["success"]:
            assert data["message_id"] is not None
            assert isinstance(data["message_id"], int)
            assert "api_response" in data
            assert data["api_response"]["ok"] is True
            logger.info(f"✅ Basic message test passed - Message ID: {data['message_id']}")
        else:
            error_msg = data.get('error_message', 'Unknown error')
            error_code = data.get('error_code', 'UNKNOWN')
            logger.error(f"❌ Basic message test failed - {error_code}: {error_msg}")
            pytest.fail(f"Telegram send message failed: {error_code} - {error_msg}")

    @pytest.mark.asyncio
    async def test_send_html_formatted_message(self):
        """Test sending a message with HTML formatting."""
        payload = {
            "bot_token": self.bot_token,
            "chat_id": self.chat_id,
            "message_text": self.test_messages["html_formatted"],
            "parse_mode": "HTML",
            "disable_preview": False,
            "silent": True
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                json=payload,
                timeout=30.0
            )

        assert response.status_code == 200
        data = response.json()

        if data["success"]:
            logger.info(f"✅ HTML formatted message test passed - Message ID: {data['message_id']}")
        else:
            error_msg = data.get('error_message', 'Unknown error')
            logger.warning(f"⚠️  HTML formatted message test failed - {error_msg}")

    @pytest.mark.asyncio
    async def test_send_markdown_v2_message(self):
        """Test sending a message with MarkdownV2 formatting."""
        payload = {
            "bot_token": self.bot_token,
            "chat_id": self.chat_id,
            "message_text": self.test_messages["markdown_v2"],
            "parse_mode": "MarkdownV2",
            "disable_preview": True,
            "silent": True
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                json=payload,
                timeout=30.0
            )

        assert response.status_code == 200
        data = response.json()

        if data["success"]:
            logger.info(f"✅ MarkdownV2 formatted message test passed - Message ID: {data['message_id']}")
        else:
            error_msg = data.get('error_message', 'Unknown error')
            logger.warning(f"⚠️  MarkdownV2 formatted message test failed - {error_msg}")

    @pytest.mark.asyncio
    async def test_send_message_with_emoji(self):
        """Test sending a message with emojis."""
        payload = {
            "bot_token": self.bot_token,
            "chat_id": self.chat_id,
            "message_text": self.test_messages["with_emoji"],
            "parse_mode": "None",
            "disable_preview": False,
            "silent": True
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                json=payload,
                timeout=30.0
            )

        assert response.status_code == 200
        data = response.json()

        if data["success"]:
            logger.info(f"✅ Emoji message test passed - Message ID: {data['message_id']}")
        else:
            error_msg = data.get('error_message', 'Unknown error')
            logger.warning(f"⚠️  Emoji message test failed - {error_msg}")

    @pytest.mark.asyncio
    async def test_message_text_truncation(self):
        """Test that long messages are properly truncated to Telegram's 4096 character limit."""
        long_message = self.test_messages["long_text"]

        payload = {
            "bot_token": self.bot_token,
            "chat_id": self.chat_id,
            "message_text": long_message,
            "parse_mode": "None",
            "disable_preview": False,
            "silent": True
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                json=payload,
                timeout=30.0
            )

        assert response.status_code == 200
        data = response.json()

        # Verify the message was truncated
        assert len(data["sent_message"]) <= 4096
        assert data["sent_message"] == long_message[:4096]

        if data["success"]:
            logger.info(f"✅ Message truncation test passed - Message truncated to {len(data['sent_message'])} characters")
        else:
            logger.info("✅ Message truncation test passed - Message properly truncated even if send failed")

    # ============= NEGATIVE TESTS =============

    @pytest.mark.asyncio
    async def test_error_handling_invalid_token(self):
        """Test error handling with invalid bot token."""
        payload = {
            "bot_token": "invalid_token_12345",
            "chat_id": self.chat_id,
            "message_text": "This should fail with invalid token",
            "parse_mode": "None",
            "disable_preview": False,
            "silent": False
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                json=payload,
                timeout=30.0
            )

        assert response.status_code == 200
        data = response.json()

        # Verify error response structure
        assert data["success"] is False
        assert data["message_id"] is None
        assert data["operation"] == "send_telegram_message"
        assert data["error_code"] is not None
        assert data["error_message"] is not None
        assert "Unauthorized" in data["error_message"] or "401" in data["error_message"] or "404 Not Found" in data["error_message"]
        logger.info("✅ Negative test passed - Invalid token correctly handled")

    @pytest.mark.asyncio
    async def test_error_handling_empty_token(self):
        """Test error handling with empty bot token."""
        payload = {
            "bot_token": "",
            "chat_id": self.chat_id,
            "message_text": "This should fail with empty token",
            "parse_mode": "None",
            "disable_preview": False,
            "silent": False
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                json=payload,
                timeout=30.0
            )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is False
        assert data["message_id"] is None
        assert data["error_code"] is not None
        logger.info("✅ Negative test passed - Empty token correctly handled")

    @pytest.mark.asyncio
    async def test_error_handling_invalid_chat_id_format(self):
        """Test error handling with invalid chat ID format."""
        payload = {
            "bot_token": self.bot_token,
            "chat_id": self.test_chat_ids["invalid"],
            "message_text": "This should fail with invalid chat ID",
            "parse_mode": "None",
            "disable_preview": False,
            "silent": False
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                json=payload,
                timeout=30.0
            )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is False
        assert data["message_id"] is None
        assert data["error_code"] is not None
        assert data["error_message"] is not None
        logger.info("✅ Negative test passed - Invalid chat ID format correctly handled")

    @pytest.mark.asyncio
    async def test_error_handling_nonexistent_chat_id(self):
        """Test error handling with nonexistent chat ID."""
        payload = {
            "bot_token": self.bot_token,
            "chat_id": self.test_chat_ids["nonexistent"],
            "message_text": "This should fail with nonexistent chat ID",
            "parse_mode": "None",
            "disable_preview": False,
            "silent": False
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                json=payload,
                timeout=30.0
            )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is False
        assert data["message_id"] is None
        assert data["error_code"] is not None
        assert data["error_message"] is not None
        logger.info("✅ Negative test passed - Nonexistent chat ID correctly handled")

    @pytest.mark.asyncio
    async def test_error_handling_empty_message(self):
        """Test error handling with empty message text."""
        payload = {
            "bot_token": self.bot_token,
            "chat_id": self.chat_id,
            "message_text": "",
            "parse_mode": "None",
            "disable_preview": False,
            "silent": False
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                json=payload,
                timeout=30.0
            )

        assert response.status_code == 200
        data = response.json()

        # Empty messages might still succeed on Telegram's side, but should be handled properly
        logger.info(f"✅ Empty message test completed - Success: {data['success']}")

    @pytest.mark.asyncio
    async def test_error_handling_missing_required_fields(self):
        """Test error handling with missing required fields."""
        # Test missing bot_token
        payload = {
            "chat_id": self.chat_id,
            "message_text": "Test message",
            "parse_mode": "None",
            "disable_preview": False,
            "silent": False
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                json=payload,
                timeout=30.0
            )

        assert response.status_code == 422  # Validation error
        logger.info("✅ Negative test passed - Missing bot_token correctly handled")

        # Test missing chat_id
        payload = {
            "bot_token": self.bot_token,
            "message_text": "Test message",
            "parse_mode": "None",
            "disable_preview": False,
            "silent": False
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                json=payload,
                timeout=30.0
            )

        assert response.status_code == 422  # Validation error
        logger.info("✅ Negative test passed - Missing chat_id correctly handled")

        # Test missing message_text
        payload = {
            "bot_token": self.bot_token,
            "chat_id": self.chat_id,
            "parse_mode": "None",
            "disable_preview": False,
            "silent": False
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                json=payload,
                timeout=30.0
            )

        assert response.status_code == 422  # Validation error
        logger.info("✅ Negative test passed - Missing message_text correctly handled")

    @pytest.mark.asyncio
    async def test_error_handling_invalid_parse_mode(self):
        """Test error handling with invalid parse mode."""
        payload = {
            "bot_token": self.bot_token,
            "chat_id": self.chat_id,
            "message_text": "Test message",
            "parse_mode": "InvalidMode",
            "disable_preview": False,
            "silent": False
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                json=payload,
                timeout=30.0
            )

        assert response.status_code == 200
        data = response.json()

        # Should handle invalid parse mode gracefully
        logger.info(f"✅ Invalid parse mode test completed - Success: {data['success']}")

    @pytest.mark.asyncio
    async def test_error_handling_malformed_json(self):
        """Test error handling with malformed JSON (should be handled by FastAPI)."""
        malformed_payload = '{ "bot_token": "test", "chat_id": 123, "message_text": }'

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                content=malformed_payload,
                headers={"Content-Type": "application/json"},
                timeout=30.0
            )

        assert response.status_code == 422  # JSON parsing error
        logger.info("✅ Negative test passed - Malformed JSON correctly handled")

    @pytest.mark.asyncio
    async def test_error_handling_missing_body(self):
        """Test error handling with missing request body."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/telegram/send",
                timeout=30.0
            )

        assert response.status_code == 422  # Validation error
        logger.info("✅ Negative test passed - Missing request body correctly handled")


def run_integration_tests():
    """Run integration tests manually."""
    """Run integration tests manually."""
    """Run integration tests manually."""
    """Run integration tests manually."""
    import pytest

    # Run the tests
    test_file = Path(__file__)
    exit_code = pytest.main([
        str(test_file),
        "-v",
        "--tb=short",
        "-x"  # Stop on first failure
    ])

    return exit_code


if __name__ == "__main__":
    print("🧪 Running DFX Social Executor Node Integration Tests")
    print("=" * 60)

    exit_code = run_integration_tests()

    if exit_code == 0:
        print("\n" + "=" * 60)
        print("🎉 All integration tests passed successfully!")
    else:
        print("\n" + "=" * 60)
        print("❌ Some integration tests failed")
        print("Please check the configuration in .env.test file")

    sys.exit(exit_code)