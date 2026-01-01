"""Output types for dfx framework."""

from typing import Any

from pydantic import BaseModel


class Output(BaseModel):
    """Output definition for a component method."""

    display_name: str
    name: str
    type_: type[Any] | None = None
    method: str | None = None

