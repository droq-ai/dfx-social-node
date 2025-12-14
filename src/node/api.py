"""FastAPI application for DFX Social Executor Node."""

import asyncio
import importlib
import json
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

# Node configuration cache
_node_config = None


def log_json(level: str, message: str, data: dict, extra_data: dict = None):
    """Log structured JSON data."""
    log_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level.upper(),
        "message": message,
        "data": data
    }

    if extra_data:
        log_entry["extra"] = extra_data

    logger.info(json.dumps(log_entry, separators=(',', ':')))
    print(f"[JSON-LOG] {json.dumps(log_entry, separators=(',', ':'))}")


def log_request_data(request: 'ExecutionRequest'):
    """Log incoming request data in JSON format."""
    request_data = {
        "request_id": request.message_id,
        "component": {
            "class": request.component_state.component_class,
            "module": request.component_state.component_module,
            "has_code": bool(request.component_state.component_code),
            "code_length": len(request.component_state.component_code or ""),
            "component_id": request.component_state.component_id,
            "display_name": request.component_state.display_name,
            "stream_topic": request.component_state.stream_topic
        },
        "execution": {
            "method_name": request.method_name,
            "is_async": request.is_async,
            "timeout": request.timeout
        },
        "parameters": sanitize_sensitive_data(request.component_state.parameters),
        "input_values": sanitize_sensitive_data(request.component_state.input_values),
        "config": sanitize_sensitive_data(request.component_state.config)
    }

    log_json("INFO", "Incoming execute request", request_data)


def log_response_data(request: 'ExecutionRequest', response: 'ExecutionResponse', execution_time: float):
    """Log response data in JSON format."""
    response_data = {
        "request_id": request.message_id,
        "execution_time_ms": round(execution_time * 1000, 2),
        "success": response.success,
        "result_type": response.result_type,
        "error": response.error,
        "response_message_id": response.message_id,
        "result_summary": get_result_summary(response.result) if response.result else None
    }

    extra_data = {
        "component_class": request.component_state.component_class,
        "method_name": request.method_name
    }

    log_json("INFO", "Execute request completed", response_data, extra_data)


def sanitize_sensitive_data(data: dict) -> dict:
    """Sanitize sensitive data like tokens and passwords for logging."""
    if not data:
        return data

    sensitive_keys = ['bot_token', 'token', 'password', 'api_key', 'secret', 'key']
    sanitized = data.copy()

    for key, value in sanitized.items():
        if key.lower() in sensitive_keys and isinstance(value, str):
            # Show first few and last few characters of tokens
            if len(value) > 10:
                sanitized[key] = f"{value[:4]}...{value[-4:]}"
            else:
                sanitized[key] = "***"

    return sanitized


def get_result_summary(result: 'Any') -> dict:
    """Get a summary of the result for logging."""
    try:
        if hasattr(result, 'data') and isinstance(result.data, dict):
            data = result.data
            return {
                "success": data.get('success'),
                "message": data.get('message'),
                "operation": data.get('operation'),
                "has_api_response": 'api_response' in data,
                "data_keys": list(data.keys()) if data else []
            }
        elif isinstance(result, dict):
            return {
                "keys": list(result.keys()),
                "success": result.get('success'),
                "message": result.get('message', 'operation')
            }
        else:
            return {
                "type": type(result).__name__,
                "string_preview": str(result)[:100] + "..." if len(str(result)) > 100 else str(result)
            }
    except Exception:
        return {
            "type": type(result).__name__,
            "preview": "Unable to summarize result"
        }


def load_node_config():
    """Load node configuration from node.json."""
    global _node_config
    if _node_config is None:
        try:
            node_config_path = os.path.join(_node_dir, "node.json")
            logger.info(f"Loading node configuration from {node_config_path}")
            with open(node_config_path, "r") as f:
                _node_config = json.load(f)
            logger.info(f"✅ Node configuration loaded: {_node_config.get('node_id')}")
        except Exception as e:
            logger.error(f"❌ Failed to load node configuration: {e}")
            _node_config = {"components": {}}
    return _node_config


async def get_nats_client():
    """Get or create NATS client instance."""
    global _nats_client
    if _nats_client is None:
        logger.info("[NATS] Creating new NATS client instance...")
        from dfx.nats_client import NATSClient
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




async def load_component_by_class_name(component_class_name: str) -> type:
    """Load component class by name using node.json configuration.

    Args:
        component_class_name: Name of the component class to load

    Returns:
        Component class type

    Raises:
        ValueError: If component cannot be loaded
    """
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
    except ModuleNotFoundError as e:
        raise ValueError(f"Module '{module_path}' not found: {e}") from e
    except AttributeError as e:
        raise ValueError(f"Component class '{component_class_name}' not found in module '{module_path}': {e}") from e


async def load_component_class(
    module_path: str, component_class: str, component_code: str | None
) -> type:
    """Load component class from module or code.

    Raises:
        ValueError: If component cannot be loaded (will be caught and returned as ExecutionResponse)
    """
    # First try to load by class name using node.json
    if component_class and not module_path and not component_code:
        try:
            return await load_component_by_class_name(component_class)
        except ValueError:
            logger.info(f"Could not load {component_class} from node.json, falling back to traditional loading")

    # Ensure dfx is in the path for imports
    node_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logger.info(f"Loading component class {component_class} from module {module_path}")
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
        # Log incoming request data in structured JSON format
        log_request_data(request)

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

            # Log component loading error response
            response = ExecutionResponse(
                result=None,
                success=False,
                result_type="ValueError",
                execution_time=execution_time,
                error=error_msg,
                message_id=request.message_id,
            )
            log_response_data(request, response, execution_time)
            return response

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

            # Log method not found error response
            response = ExecutionResponse(
                result=None,
                success=False,
                result_type="AttributeError",
                execution_time=execution_time,
                error=error_msg,
                message_id=request.message_id,
            )
            log_response_data(request, response, execution_time)
            return response

        method = getattr(component, request.method_name)

        # Check if method is async or sync
        import inspect
        is_coroutine = inspect.iscoroutinefunction(method)
        logger.info(f"[EXECUTION] Method {request.method_name} is async: {is_coroutine}")
        print(f"[EXECUTION] Method {request.method_name} is async: {is_coroutine}")

        # Execute method
        if request.is_async:
            if is_coroutine:
                # Method is async, call it directly
                result = await asyncio.wait_for(method(), timeout=request.timeout)
            else:
                # Method is sync, run in thread
                result = await asyncio.wait_for(
                    asyncio.to_thread(method), timeout=request.timeout
                )
        else:
            # Request wants sync execution
            if is_coroutine:
                # Method is async but request wants sync - await it anyway
                logger.warning(f"[EXECUTION] Method {request.method_name} is async but request.is_async=false. Awaiting anyway.")
                print(f"[EXECUTION] WARNING: Method {request.method_name} is async but request.is_async=false. Awaiting anyway.")
                result = await asyncio.wait_for(method(), timeout=request.timeout)
            else:
                # Method is sync, run in thread
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

        # Log successful response
        response = ExecutionResponse(
            result=serialized_result,
            success=True,
            result_type=type(result).__name__,
            execution_time=execution_time,
            message_id=message_id,
        )
        log_response_data(request, response, execution_time)
        return response

    except asyncio.TimeoutError:
        execution_time = time.time() - start_time
        error_msg = f"Execution timed out after {request.timeout}s"
        logger.error(error_msg)

        # Log timeout response
        response = ExecutionResponse(
            result=None,
            success=False,
            result_type="TimeoutError",
            execution_time=execution_time,
            error=error_msg,
            message_id=request.message_id,
        )
        log_response_data(request, response, execution_time)
        return response

    except HTTPException:
        raise

    except Exception as e:
        execution_time = time.time() - start_time
        error_msg = f"Execution failed: {type(e).__name__}: {str(e)}"
        logger.error(error_msg, exc_info=True)

        # Log error response
        response = ExecutionResponse(
            result=None,
            success=False,
            result_type=type(e).__name__,
            execution_time=execution_time,
            error=error_msg,
            message_id=request.message_id,
        )
        log_response_data(request, response, execution_time)
        return response


# Note: Telegram-specific endpoints have been removed in favor of the standardized /api/v1/execute endpoint
# Use the component execution endpoint to call Telegram components:
# POST /api/v1/execute with component_class: "DFXTelegramComponent" and method_name: "send_message"


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
        "endpoints": "api/v1/execute, health, /"
    }