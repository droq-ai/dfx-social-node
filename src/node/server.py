"""HTTP server for handling incoming requests to the DFX Social Executor Node."""

import json
import logging
import os
import ssl
import sys
from typing import Any

import aiohttp.web
from aiohttp import web

logger = logging.getLogger(__name__)

# Node configuration cache
_node_config = None


def load_node_config():
    """Load node configuration from node.json."""
    global _node_config
    if _node_config is None:
        try:
            node_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            node_config_path = os.path.join(node_dir, "node.json")
            logger.info(f"Loading node configuration from {node_config_path}")
            with open(node_config_path, "r") as f:
                _node_config = json.load(f)
            logger.info(f"✅ Node configuration loaded: {_node_config.get('node_id')}")
        except Exception as e:
            logger.error(f"❌ Failed to load node configuration: {e}")
            _node_config = {"components": {}}
    return _node_config


async def load_component_by_class_name(component_class_name: str) -> type:
    """Load component class by name using node.json configuration.

    Args:
        component_class_name: Name of the component class to load

    Returns:
        Component class type

    Raises:
        ValueError: If component cannot be loaded
    """
    import importlib

    node_config = load_node_config()
    components = node_config.get("components", {})

    # Find component by class name in node.json
    component_info = None
    for name, info in components.items():
        if name == component_class_name:
            component_info = info
            break

    if not component_info:
        raise ValueError(f"Component '{component_class_name}' not found in node.json configuration")

    module_path = component_info.get("path")
    if not module_path:
        raise ValueError(f"No module path specified for component '{component_class_name}'")

    # Ensure dfx is in the path for imports
    node_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if node_dir not in sys.path:
        sys.path.insert(0, node_dir)

    logger.info(f"Loading component {component_class_name} from module {module_path}")

    try:
        module = importlib.import_module(module_path)
        component_class_obj = getattr(module, component_class_name)
        logger.info(f"✅ Loaded {component_class_name} from module {module_path}")
        return component_class_obj
    except Exception as e:
        logger.error(f"Failed to load {component_class_name}: {e}")
        raise ValueError(f"Failed to load component '{component_class_name}': {e}")


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
        """Handle status endpoint using component-based approach."""
        try:
            # Try to load DFX Telegram component using node.json
            component_class = await load_component_by_class_name("DFXTelegramMessageComponent")

            # Check available methods
            has_send_message = hasattr(component_class, 'send_message')
            has_get_bot_info = hasattr(component_class, 'get_bot_info')

            return web.json_response({
                "status": "running",
                "telegram_enabled": True,
                "telegram_component": "DFXTelegramMessageComponent",
                "telegram_functions": {
                    "send_message": has_send_message,
                    "get_bot_info": has_get_bot_info
                },
                "component_loading": "node_json_based"
            })
        except Exception as e:
            logger.warning(f"Could not load DFX Telegram component: {e}")
            return web.json_response({
                "status": "running",
                "telegram_enabled": False,
                "telegram_component": None,
                "telegram_functions": {
                    "send_message": False,
                    "get_bot_info": False
                },
                "component_loading": "failed",
                "error": str(e)
            })

    async def _handle_telegram_send(self, request: web.Request) -> web.Response:
        """Handle Telegram send message endpoint using component-based approach."""
        try:
            data = await request.json()

            # Try to use DFX Telegram component via node.json
            component_class = await load_component_by_class_name("DFXTelegramMessageComponent")

            # Extract parameters from request data
            bot_token = data.get("bot_token")
            chat_id = data.get("chat_id")
            message_text = data.get("message_text", data.get("text", ""))
            parse_mode = data.get("parse_mode", "")
            disable_preview = data.get("disable_preview", False)
            silent = data.get("silent", False)

            # Instantiate the component
            component = component_class(
                bot_token=bot_token,
                chat_id=chat_id,
                text=message_text[:4096],  # Truncate to Telegram limit
                parse_mode=parse_mode if parse_mode != "None" else "",
                disable_web_page_preview="True" if disable_preview else "False",
                disable_notification="True" if silent else "False"
            )

            # Execute the component's send_message method
            result = await component.send_message()

            # Extract data from the Data object
            if hasattr(result, 'data'):
                result_data = result.data
            else:
                result_data = result

            return web.json_response(result_data)

        except Exception as e:
            logger.error(f"Error handling Telegram send request: {e}")
            return web.json_response({
                "success": False,
                "error": str(e),
                "operation": "send_telegram_message"
            }, status=500)

    async def _handle_telegram_bot_info(self, request: web.Request) -> web.Response:
        """Handle Telegram bot info endpoint using component-based approach."""
        try:
            data = await request.json() if request.can_read_body else {}

            # Try to use DFX Telegram component via node.json
            component_class = await load_component_by_class_name("DFXTelegramMessageComponent")

            # Check if the component has get_bot_info method
            if hasattr(component_class, 'get_bot_info'):
                bot_token = data.get("bot_token")

                # Instantiate the component
                component = component_class(bot_token=bot_token)

                # Execute the component's get_bot_info method
                result = await component.get_bot_info()

                # Extract data from the Data object
                if hasattr(result, 'data'):
                    result_data = result.data
                else:
                    result_data = result

                return web.json_response(result_data)
            else:
                # Component doesn't have get_bot_info method
                return web.json_response({
                    "success": False,
                    "error": "DFXTelegramMessageComponent does not have get_bot_info method",
                    "operation": "get_telegram_bot_info"
                }, status=501)  # Not Implemented

        except Exception as e:
            logger.error(f"Error handling Telegram bot info request: {e}")
            return web.json_response({
                "success": False,
                "error": str(e),
                "operation": "get_telegram_bot_info"
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