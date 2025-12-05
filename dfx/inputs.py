"""Input types for dfx framework."""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class BaseInput(BaseModel):
    """Base input class."""

    name: str
    display_name: str
    info: str = ""
    value: Any = None
    required: bool = False
    field_type: str = "str"


class FloatInput(BaseInput):
    """Float input field."""

    field_type: str = "float"
    value: float = Field(default=0.0)

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any) -> float:
        """Validate and convert to float."""
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        try:
            return float(v)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid float value: {v}") from e


class IntInput(BaseInput):
    """Integer input field."""

    field_type: str = "int"
    value: int = Field(default=0)

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any) -> int:
        """Validate and convert to int."""
        if v is None:
            return 0
        if isinstance(v, (int, float)):
            return int(v)
        try:
            return int(v)
        except (ValueError, TypeError) as e:
            raise ValueError(f"Invalid int value: {v}") from e


class StrInput(BaseInput):
    """String input field."""

    field_type: str = "str"
    value: str = Field(default="")

    @field_validator("value")
    @classmethod
    def validate_value(cls, v: Any) -> str:
        """Validate and convert to string."""
        if v is None:
            return ""
        return str(v)

