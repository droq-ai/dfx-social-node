#!/usr/bin/env python3
"""
Main entry point for the node.

This is an agnostic template - replace this with your node logic.
Includes examples for NATS JetStream and HTTP I/O.
"""

import asyncio
import logging
import os
import signal
import sys

# Optional: Use the logger helper
try:
    from .logger import setup_logging
except ImportError:
    setup_logging = None

# Optional: Import NATS and HTTP clients
try:
    from .nats import NATSClient
except ImportError:
    NATSClient = None

try:
    from .http import HTTPClient
except ImportError:
    HTTPClient = None

# Optional: Import Telegram integration
try:
    from social.telegram.message import send_message, get_bot_info
except ImportError:
    send_message = None
    get_bot_info = None


# Global flag for graceful shutdown
shutdown_event = asyncio.Event()


async def handle_telegram_message(data: dict, headers: dict):
    """Handle Telegram-specific messages from NATS.

    Args:
        data: Message data containing Telegram request
        headers: Message headers
    """
    logger = logging.getLogger(__name__)

    # Get the subject from headers or infer from data
    subject = headers.get("subject", "")
    response_subject = headers.get("reply", "")

    try:
        result = None

        if "send_message" in subject and send_message:
            result = await send_message(data)
        elif "get_bot_info" in subject and get_bot_info:
            result = await get_bot_info(data)
        else:
            result = {"success": False, "error": "Unknown Telegram operation"}

        # Send response if reply subject is provided
        if response_subject and nats_client:
            await nats_client.publish(response_subject, result)
            logger.debug(f"Sent Telegram response to {response_subject}")

    except Exception as e:
        logger.error(f"Error handling Telegram message: {e}", exc_info=True)
        # Send error response if possible
        if response_subject and nats_client:
            error_response = {
                "success": False,
                "error": f"Internal error: {e}"
            }
            await nats_client.publish(response_subject, error_response)


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logging.info(f"Received signal {signum}, initiating shutdown...")
    shutdown_event.set()


async def run_node():
    """
    Main node logic.

    Replace this function with your actual node implementation.
    Examples below show how to use NATS JetStream and HTTP clients.
    """
    logger = logging.getLogger(__name__)
    logger.info("Node starting...")

    # Example: Read environment variables
    node_name = os.getenv("NODE_NAME", "droq-node")
    log_level = os.getenv("LOG_LEVEL", "INFO")

    logger.info(f"Node name: {node_name}")
    logger.info(f"Log level: {log_level}")

    # Initialize clients
    nats_client = None
    http_client = None

    try:
        # Example 1: Connect to NATS JetStream
        if NATSClient:
            try:
                nats_client = NATSClient()
                await nats_client.connect()
                logger.info("Connected to NATS JetStream")
            except Exception as e:
                logger.warning(
                    f"Could not connect to NATS (this is OK if NATS is not running): {e}"
                )
                nats_client = None

            # Example: Subscribe to messages
            async def handle_message(data: dict, headers: dict):
                """Handle incoming NATS messages."""
                logger.info(f"Received message: {data}")
                # Process your message here

            # Example: Subscribe to messages
            async def handle_message(data: dict, headers: dict):
                """Handle incoming NATS messages."""
                logger.info(f"Received message: {data}")

                # Handle Telegram messages
                if isinstance(data, dict):
                    await handle_telegram_message(data, headers)

            # Subscribe to Telegram message subjects (runs in background)
            if send_message or get_bot_info:
                asyncio.create_task(
                    nats_client.subscribe("telegram.send_message", handle_message, queue="telegram-queue")
                )
                asyncio.create_task(
                    nats_client.subscribe("telegram.get_bot_info", handle_message, queue="telegram-queue")
                )
                logger.info("Subscribed to Telegram message subjects")

            # Example: Publish a message
            # await nats_client.publish(
            #     "output",
            #     {"message": "Hello from node", "timestamp": "2024-01-01T00:00:00Z"}
            # )

        # Example 2: Use HTTP client
        if HTTPClient:
            http_client = HTTPClient()
            logger.info("HTTP client initialized")

            # Telegram functions are available if the social module is present
            if send_message and get_bot_info:
                logger.info("Telegram message functions available")

        # Main processing loop
        while not shutdown_event.is_set():
            logger.debug("Node running...")

            # Your processing logic here
            # Examples:
            # - Process messages from NATS
            # - Poll APIs and publish to NATS
            # - Transform data between systems
            # - Connect to databases
            # - etc.

            # Example: Publish periodic updates
            # if nats_client:
            #     await nats_client.publish(
            #         "status",
            #         {"status": "running", "node": node_name}
            #     )

            # Wait a bit before next iteration
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=1.0)
            except TimeoutError:
                continue

    except Exception as e:
        logger.error(f"Error in node execution: {e}", exc_info=True)
        raise
    finally:
        # Cleanup
        if nats_client:
            await nats_client.close()
        if http_client:
            await http_client.close()
        logger.info("Node shutting down...")


def main():
    """
    Main entry point.

    Sets up logging, signal handlers, and runs the node.
    """
    # Setup logging
    if setup_logging:
        setup_logging()
    else:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    logger = logging.getLogger(__name__)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Run the node
        asyncio.run(run_node())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
