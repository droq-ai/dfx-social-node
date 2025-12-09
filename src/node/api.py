"""FastAPI application for DFX Social Executor Node."""

import asyncio
import importlib
import logging
import os
import sys
import time
import uuid
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# dfx framework is at the root of the repo - ensure it's in the path
_node_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _node_dir not in sys.path:
    sys.path.insert(0, _node_dir)

logger = logging.getLogger(__name__)

app = FastAPI(title="DFX Social Executor Node", version="0.1.0")

# Initialize NATS client (lazy connection)
_nats_client = None


async def get_nats_client():
    """Get or create NATS client instance."""
    global _nats_client
    if _nats_client is None:
        logger.info("[NATS] Creating new NATS client instance...")
        from dfx.nats import NATSClient
        nats_url = os.getenv("NATS_URL", "nats://localhost:4222")
        logger.info(f"[NATS] Connecting to NATS at {nats_url}")
        _nats_client = NATSClient(nats_url=nats_url)
        try:
            await _nats_client.connect()
            logger.info("[NATS] ✅ Successfully connected to NATS")
        except Exception as e:
            logger.warning(f"[NATS] ❌ Failed to connect to NATS (non-critical): {e}", exc_info=True)
            _nats_client = None
    else:
        logger.debug("[NATS] Using existing NATS client instance")
    return _nats_client


class ComponentState(BaseModel):
    """Component state for execution."""

    component_class: str
    component_module: str
    component_code: str | None = None
    parameters: dict[str, Any]
    input_values: dict[str, Any] | None = None
    config: dict[str, Any] | None = None
    display_name: str | None = None
    component_id: str | None = None
    stream_topic: str | None = None


class ExecutionRequest(BaseModel):
    """Request to execute a component method."""

    component_state: ComponentState
    method_name: str
    is_async: bool = False
    timeout: int = 30
    message_id: str | None = None


class ExecutionResponse(BaseModel):
    """Response from component execution."""

    result: Any
    success: bool
    result_type: str
    execution_time: float
    error: str | None = None
    message_id: str | None = None


class TelegramSendMessageRequest(BaseModel):
    """Request to send Telegram message."""

    bot_token: str
    chat_id: str
    message_text: str
    parse_mode: str = "None"
    disable_preview: bool = False
    silent: bool = False


class TelegramBotInfoRequest(BaseModel):
    """Request to get Telegram bot info."""

    bot_token: str


async def load_component_class(
    module_path: str, component_class: str, component_code: str | None
) -> type:
    """Load component class from module or code.

    Raises:
        ValueError: If component cannot be loaded (will be caught and returned as ExecutionResponse)
    """
    # Ensure dfx is in the path for imports
    node_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if node_dir not in sys.path:
        sys.path.insert(0, node_dir)

    # Try to import from module first
    if module_path and not component_code:
        try:
            module = importlib.import_module(module_path)
            component_class_obj = getattr(module, component_class)
            logger.info(f"Loaded {component_class} from module {module_path}")
            return component_class_obj
        except ModuleNotFoundError as e:
            raise ValueError(f"Module '{module_path}' not found: {e}") from e
        except AttributeError as e:
            raise ValueError(f"Component class '{component_class}' not found in module '{module_path}': {e}") from e

    # If code is provided, execute it
    if component_code:
        try:
            # Create a namespace for the code execution with dfx available
            namespace = {"dfx": __import__("dfx")}
            exec(component_code, namespace)
            component_class_obj = namespace.get(component_class)
            if component_class_obj:
                logger.info(f"Loaded {component_class} from provided code")
                return component_class_obj
            raise ValueError(f"Component class {component_class} not found in provided code")
        except Exception as e:
            raise ValueError(f"Failed to execute component code: {e}") from e

    raise ValueError("Could not load component: no module path or code provided")


def serialize_result(result: Any) -> Any:
    """Serialize result to JSON-serializable format."""
    if result is None:
        return None

    # If it's a Data object (dfx or lfx), extract its data dict
    if hasattr(result, "data"):
        if hasattr(result, "model_dump"):
            try:
                return result.model_dump()
            except Exception:
                pass
        # Fallback: extract data dict directly
        if isinstance(result.data, dict):
            return {"data": result.data, "text_key": getattr(result, "text_key", "text")}
        return {"data": result.data if hasattr(result, "data") else str(result)}

    # If it's a Pydantic model, try model_dump
    if hasattr(result, "model_dump"):
        try:
            return result.model_dump()
        except Exception:
            pass

    # If it's a dict, recursively serialize
    if isinstance(result, dict):
        return {k: serialize_result(v) for k, v in result.items()}

    # If it's a list, recursively serialize
    if isinstance(result, list):
        return [serialize_result(item) for item in result]

    # For primitives, return as-is
    if isinstance(result, (str, int, float, bool)):
        return result

    # For other types, convert to string
    return str(result)


@app.post("/api/v1/execute", response_model=ExecutionResponse)
async def execute_component(request: ExecutionRequest) -> ExecutionResponse:
    """Execute a social component method."""
    start_time = time.time()

    try:
        # Log what we received
        stream_topic_value = request.component_state.stream_topic
        log_msg = (
            f"Received execution request: "
            f"class={request.component_state.component_class}, "
            f"module={request.component_state.component_module}, "
            f"code_length={len(request.component_state.component_code or '') if request.component_state.component_code else 0}, "
            f"stream_topic={stream_topic_value}"
        )
        logger.info(log_msg)
        print(f"[EXECUTOR] {log_msg}")

        # Load component class
        try:
            component_class = await load_component_class(
                request.component_state.component_module,
                request.component_state.component_class,
                request.component_state.component_code,
            )
        except ValueError as e:
            # Component loading failed - return error response instead of HTTPException
            execution_time = time.time() - start_time
            error_msg = f"Failed to load component class: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return ExecutionResponse(
                result=None,
                success=False,
                result_type="ValueError",
                execution_time=execution_time,
                error=error_msg,
                message_id=request.message_id,
            )

        # Instantiate component with parameters
        component_params = request.component_state.parameters.copy()

        # Merge input_values if provided
        if request.component_state.input_values:
            component_params.update(request.component_state.input_values)

        if request.component_state.config:
            for key, value in request.component_state.config.items():
                component_params[f"_{key}"] = value

        component = component_class(**component_params)

        # Get the method
        if not hasattr(component, request.method_name):
            execution_time = time.time() - start_time
            error_msg = f"Method {request.method_name} not found on component {request.component_state.component_class}"
            logger.error(error_msg)
            return ExecutionResponse(
                result=None,
                success=False,
                result_type="AttributeError",
                execution_time=execution_time,
                error=error_msg,
                message_id=request.message_id,
            )

        method = getattr(component, request.method_name)

        # Execute method
        if request.is_async:
            result = await asyncio.wait_for(method(), timeout=request.timeout)
        else:
            result = await asyncio.wait_for(
                asyncio.to_thread(method), timeout=request.timeout
            )

        execution_time = time.time() - start_time

        # Serialize result
        serialized_result = serialize_result(result)

        logger.info(
            f"Method {request.method_name} completed successfully "
            f"in {execution_time:.3f}s, result type: {type(result).__name__}"
        )

        # Use message_id from request (generated by backend) or generate one if not provided
        message_id = request.message_id or str(uuid.uuid4())

        # Publish result to NATS stream if topic is provided
        if request.component_state.stream_topic:
            topic = request.component_state.stream_topic
            logger.info(f"[NATS] Attempting to publish to topic: {topic} with message_id: {message_id}")
            print(f"[NATS] Attempting to publish to topic: {topic} with message_id: {message_id}")
            try:
                nats_client = await get_nats_client()
                if nats_client:
                    logger.info("[NATS] NATS client obtained, preparing publish data...")
                    print("[NATS] NATS client obtained, preparing publish data...")
                    # Publish result to NATS with message ID from backend
                    publish_data = {
                        "message_id": message_id,
                        "component_id": request.component_state.component_id,
                        "component_class": request.component_state.component_class,
                        "result": serialized_result,
                        "result_type": type(result).__name__,
                        "execution_time": execution_time,
                    }
                    logger.info(f"[NATS] Publishing to topic: {topic}, message_id: {message_id}, data keys: {list(publish_data.keys())}")
                    print(f"[NATS] Publishing to topic: {topic}, message_id: {message_id}, data keys: {list(publish_data.keys())}")
                    # Use the topic directly
                    await nats_client.publish(
                        subject=topic,
                        data=publish_data,
                    )
                    logger.info(f"[NATS] ✅ Successfully published result to NATS topic: {topic} with message_id: {message_id}")
                    print(f"[NATS] ✅ Successfully published result to NATS topic: {topic} with message_id: {message_id}")
                else:
                    logger.warning("[NATS] NATS client is None, cannot publish")
                    print("[NATS] ⚠️  NATS client is None, cannot publish")
            except Exception as e:
                # Non-critical: log but don't fail execution
                logger.warning(f"[NATS] ❌ Failed to publish to NATS (non-critical): {e}", exc_info=True)
                print(f"[NATS] ❌ Failed to publish to NATS (non-critical): {e}")

        return ExecutionResponse(
            result=serialized_result,
            success=True,
            result_type=type(result).__name__,
            execution_time=execution_time,
            message_id=message_id,
        )

    except asyncio.TimeoutError:
        execution_time = time.time() - start_time
        error_msg = f"Execution timed out after {request.timeout}s"
        logger.error(error_msg)
        return ExecutionResponse(
            result=None,
            success=False,
            result_type="TimeoutError",
            execution_time=execution_time,
            error=error_msg,
            message_id=request.message_id,
        )

    except HTTPException:
        raise

    except Exception as e:
        execution_time = time.time() - start_time
        error_msg = f"Execution failed: {type(e).__name__}: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return ExecutionResponse(
            result=None,
            success=False,
            result_type=type(e).__name__,
            execution_time=execution_time,
            error=error_msg,
            message_id=request.message_id,
        )


@app.post("/api/v1/telegram/send", response_model=dict)
async def send_telegram_message(request: TelegramSendMessageRequest) -> dict:
    """Send Telegram message directly."""
    try:
        # Prepare data for Telegram API call
        telegram_data = {
            "bot_token": request.bot_token,
            "chat_id": request.chat_id,
            "message_text": request.message_text[:4096],  # Truncate to Telegram limit
            "parse_mode": request.parse_mode if request.parse_mode != "None" else None,
            "disable_preview": request.disable_preview,
            "silent": request.silent,
        }

        # Try to use the existing Telegram message function if available
        try:
            from social.telegram.message import send_message
            result = await send_message(telegram_data)
            logger.info(f"Telegram message sent successfully via component: {result}")
            return result
        except ImportError:
            # Fallback to direct HTTP call
            logger.info("Telegram component not available, using direct HTTP call")

            url = f"https://api.telegram.org/bot{request.bot_token}/sendMessage"

            # Prepare Telegram API payload
            payload = {
                "chat_id": request.chat_id,
                "text": request.message_text[:4096],  # Telegram limit
            }

            if request.parse_mode != "None":
                payload["parse_mode"] = request.parse_mode

            if request.disable_preview:
                payload["disable_web_page_preview"] = True

            if request.silent:
                payload["disable_notification"] = True

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()

                api_response = response.json()

                if api_response.get("ok"):
                    return {
                        "success": True,
                        "message_id": api_response["result"]["message_id"],
                        "chat_id": str(api_response["result"]["chat"]["id"]),
                        "sent_message": request.message_text[:4096],
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "api_response": api_response,
                        "error_code": None,
                        "error_message": None,
                        "operation": "send_telegram_message"
                    }
                else:
                    return {
                        "success": False,
                        "message_id": None,
                        "chat_id": request.chat_id,
                        "sent_message": request.message_text[:4096],
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "api_response": api_response,
                        "error_code": api_response.get("error_code"),
                        "error_message": api_response.get("description"),
                        "operation": "send_telegram_message"
                    }

    except httpx.HTTPError as e:
        logger.error(f"HTTP error sending Telegram message: {e}")
        return {
            "success": False,
            "message_id": None,
            "chat_id": request.chat_id,
            "sent_message": request.message_text[:4096],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "api_response": None,
            "error_code": "HTTP_ERROR",
            "error_message": str(e),
            "operation": "send_telegram_message"
        }
    except Exception as e:
        logger.error(f"Error sending Telegram message: {e}", exc_info=True)
        return {
            "success": False,
            "message_id": None,
            "chat_id": request.chat_id,
            "sent_message": request.message_text[:4096],
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "api_response": None,
            "error_code": "INTERNAL_ERROR",
            "error_message": str(e),
            "operation": "send_telegram_message"
        }


@app.post("/api/v1/telegram/bot-info", response_model=dict)
async def get_telegram_bot_info(request: TelegramBotInfoRequest) -> dict:
    """Get Telegram bot information."""
    try:
        # Try to use the existing Telegram bot info function if available
        try:
            from social.telegram.message import get_bot_info
            result = await get_bot_info({"bot_token": request.bot_token})
            logger.info(f"Telegram bot info retrieved successfully via component: {result}")
            return result
        except ImportError:
            # Fallback to direct HTTP call
            logger.info("Telegram component not available, using direct HTTP call")

            url = f"https://api.telegram.org/bot{request.bot_token}/getMe"

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()

                api_response = response.json()

                if api_response.get("ok"):
                    bot_info = api_response["result"]
                    return {
                        "success": True,
                        "bot_info": {
                            "id": bot_info["id"],
                            "username": bot_info["username"],
                            "first_name": bot_info["first_name"],
                            "last_name": bot_info.get("last_name"),
                            "is_bot": bot_info["is_bot"],
                            "can_read_all_group_messages": bot_info.get("can_read_all_group_messages", False),
                            "supports_inline_queries": bot_info.get("supports_inline_queries", False),
                        },
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "api_response": api_response,
                        "error_code": None,
                        "error_message": None,
                        "operation": "get_telegram_bot_info"
                    }
                else:
                    return {
                        "success": False,
                        "bot_info": None,
                        "timestamp": datetime.utcnow().isoformat() + "Z",
                        "api_response": api_response,
                        "error_code": api_response.get("error_code"),
                        "error_message": api_response.get("description"),
                        "operation": "get_telegram_bot_info"
                    }

    except httpx.HTTPError as e:
        logger.error(f"HTTP error getting Telegram bot info: {e}")
        return {
            "success": False,
            "bot_info": None,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "api_response": None,
            "error_code": "HTTP_ERROR",
            "error_message": str(e),
            "operation": "get_telegram_bot_info"
        }
    except Exception as e:
        logger.error(f"Error getting Telegram bot info: {e}", exc_info=True)
        return {
            "success": False,
            "bot_info": None,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "api_response": None,
            "error_code": "INTERNAL_ERROR",
            "error_message": str(e),
            "operation": "get_telegram_bot_info"
        }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": "dfx-social-executor-node"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "dfx-social-executor-node",
        "version": "0.1.0",
        "description": "DFX Social Executor Node for Telegram messaging",
        "endpoints": "api/v1/execute, api/v1/telegram/send, api/v1/telegram/bot-info, health, /"
    }