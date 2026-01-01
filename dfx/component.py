"""Base Component class for dfx framework."""

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict

from dfx.inputs import BaseInput
from dfx.outputs import Output

logger = logging.getLogger(__name__)


class Component(BaseModel):
    """Base component class for dfx framework.
    
    Components should inherit from this class and define:
    - display_name: Display name for the component
    - description: Description of what the component does
    - icon: Icon name (optional)
    - name: Component class name
    - inputs: List of Input objects
    - outputs: List of Output objects
    """

    model_config = ConfigDict(extra="allow")  # Allow extra fields for dynamic input values

    display_name: str = ""
    description: str = ""
    icon: str = ""
    name: str = ""
    inputs: list[BaseInput] = []
    outputs: list[Output] = []

    # Internal state
    _status: str = ""
    _logs: list[str] = []

    def __init__(self, **kwargs):
        """Initialize component with parameters."""
        # Extract config values (keys starting with _)
        config = {k: v for k, v in kwargs.items() if k.startswith("_")}

        # Get class-level inputs/outputs if not provided in kwargs
        model_kwargs = {}
        if "inputs" not in kwargs and hasattr(self.__class__, "inputs"):
            model_kwargs["inputs"] = self.__class__.inputs
        if "outputs" not in kwargs and hasattr(self.__class__, "outputs"):
            model_kwargs["outputs"] = self.__class__.outputs
        if "display_name" not in kwargs and hasattr(self.__class__, "display_name"):
            model_kwargs["display_name"] = self.__class__.display_name
        if "description" not in kwargs and hasattr(self.__class__, "description"):
            model_kwargs["description"] = self.__class__.description
        if "icon" not in kwargs and hasattr(self.__class__, "icon"):
            model_kwargs["icon"] = self.__class__.icon
        if "name" not in kwargs and hasattr(self.__class__, "name"):
            model_kwargs["name"] = self.__class__.name or self.__class__.__name__

        # Merge with kwargs (this includes input values like number1, number2)
        # With extra="allow", Pydantic will accept these extra fields
        model_kwargs.update(kwargs)

        # Initialize base model first (with all kwargs, including extra fields)
        super().__init__(**model_kwargs)

        # Set default input values if not provided
        for input_def in self.inputs:
            input_name = input_def.name
            if not hasattr(self, input_name) or getattr(self, input_name, None) is None:
                if hasattr(input_def, "value") and input_def.value is not None:
                    setattr(self, input_name, input_def.value)
                else:
                    # Set default based on type
                    if hasattr(input_def, "field_type"):
                        if input_def.field_type == "float":
                            setattr(self, input_name, 0.0)
                        elif input_def.field_type == "int":
                            setattr(self, input_name, 0)
                        else:
                            setattr(self, input_name, "")

        # Store config
        self._config = config

        # Initialize status
        self._status = ""
        self._logs = []

    @property
    def status(self) -> str:
        """Get component status."""
        return self._status

    @status.setter
    def status(self, value: str) -> None:
        """Set component status."""
        self._status = str(value)

    def log(self, message: str) -> None:
        """Log a message."""
        log_msg = f"[{self.__class__.__name__}] {message}"
        self._logs.append(log_msg)
        logger.info(log_msg)

    def build(self) -> Any:
        """Build method - should be overridden by subclasses.
        
        Returns the main execution method or result.
        """
        # Default: return the first output method if available
        if self.outputs and self.outputs[0].method:
            return getattr(self, self.outputs[0].method, None)
        return None

