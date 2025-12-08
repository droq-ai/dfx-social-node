"""HTTP server for handling incoming requests to the DFX Social Executor Node."""

import logging
import ssl
from typing import Any

import aiohttp.web
from aiohttp import web

logger = logging.getLogger(__name__)


class HTTPServer:
    """HTTP server wrapper for handling incoming requests."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8007,
        ssl_context: ssl.SSLContext | None = None,
    ):
        """
        Initialize HTTP server.

        Args:
            host: Host to bind to
            port: Port to bind to
            ssl_context: SSL context for HTTPS
        """
        self.host = host
        self.port = port
        self.ssl_context = ssl_context
        self.app = web.Application()
        self.runner: web.AppRunner | None = None
        self.site: web.TCPSite | None = None

        # Setup routes
        self._setup_routes()

    def _setup_routes(self):
        """Setup HTTP routes."""
        self.app.router.add_get("/", self._handle_root)
        self.app.router.add_get("/health", self._handle_health)
        self.app.router.add_get("/status", self._handle_status)
        self.app.router.add_post("/telegram/send", self._handle_telegram_send)
        self.app.router.add_get("/telegram/bot-info", self._handle_telegram_bot_info)

    async def _handle_root(self, request: web.Request) -> web.Response:
        """Handle root endpoint."""
        return web.json_response({
            "name": "DFX Social Executor Node",
            "status": "running",
            "endpoints": [
                "/",
                "/health",
                "/status",
                "/telegram/send",
                "/telegram/bot-info"
            ]
        })

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Handle health check endpoint."""
        return web.json_response({
            "status": "healthy",
            "timestamp": "2025-12-08T00:00:00Z"  # You might want to use actual timestamp
        })

    async def _handle_status(self, request: web.Request) -> web.Response:
        """Handle status endpoint."""
        try:
            # Try to import and check if Telegram functions are available
            from social.telegram.message import send_message, get_bot_info

            return web.json_response({
                "status": "running",
                "telegram_enabled": True,
                "telegram_functions": {
                    "send_message": send_message is not None,
                    "get_bot_info": get_bot_info is not None
                }
            })
        except ImportError:
            return web.json_response({
                "status": "running",
                "telegram_enabled": False,
                "telegram_functions": {
                    "send_message": False,
                    "get_bot_info": False
                }
            })

    async def _handle_telegram_send(self, request: web.Request) -> web.Response:
        """Handle Telegram send message endpoint."""
        try:
            from social.telegram.message import send_message
            if not send_message:
                raise ImportError("send_message function not available")

            data = await request.json()
            result = await send_message(data)
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Error handling Telegram send request: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def _handle_telegram_bot_info(self, request: web.Request) -> web.Response:
        """Handle Telegram bot info endpoint."""
        try:
            from social.telegram.message import get_bot_info
            if not get_bot_info:
                raise ImportError("get_bot_info function not available")

            data = await request.json() if request.can_read_body else {}
            result = await get_bot_info(data)
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Error handling Telegram bot info request: {e}")
            return web.json_response({
                "success": False,
                "error": str(e)
            }, status=500)

    async def start(self) -> None:
        """Start HTTP server."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()

            self.site = web.TCPSite(
                runner=self.runner,
                host=self.host,
                port=self.port,
                ssl_context=self.ssl_context
            )
            await self.site.start()

            protocol = "https" if self.ssl_context else "http"
            logger.info(f"HTTP server started at {protocol}://{self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to start HTTP server: {e}")
            raise

    async def stop(self) -> None:
        """Stop HTTP server."""
        if self.runner:
            await self.runner.cleanup()
            logger.info("HTTP server stopped")

    @staticmethod
    def create_ssl_context(cert_file: str, key_file: str) -> ssl.SSLContext:
        """
        Create SSL context for HTTPS.

        Args:
            cert_file: Path to certificate file
            key_file: Path to private key file

        Returns:
            SSL context
        """
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_file, key_file)
        return ssl_context