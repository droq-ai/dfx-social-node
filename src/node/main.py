"""Main entry point for DFX Social Executor Node."""

import asyncio
import logging
import sys

import uvicorn

from node.api import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global shutdown event for testing
shutdown_event = asyncio.Event()


async def run_node():
    """Run the node with graceful shutdown support."""
    host = "0.0.0.0"
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8007

    logger.info(f"Starting DFX Social Executor Node on {host}:{port}")

    # Configure uvicorn server
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    # Run server with shutdown handling
    async with server:
        await server.serve()


def main():
    """Run the FastAPI application."""
    host = "0.0.0.0"
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8007

    logger.info(f"Starting DFX Social Executor Node on {host}:{port}")

    # Configure uvicorn to run on both HTTP and HTTPS
    # For HTTPS with self-signed certificate, we'll need to add SSL context
    # For now, running on HTTP
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
