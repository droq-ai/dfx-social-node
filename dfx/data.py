"""Simplified Data class for dfx framework."""

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class Data(BaseModel):
    """Represents a record with text and optional data.
    
    Attributes:
        data (dict): Additional data associated with the record.
        text_key (str): Key used to access text in the data dict.
        default_value (str | None): Default value if text_key is not found.
    """

    model_config = ConfigDict(validate_assignment=True)

    text_key: str = "text"
    data: dict[str, Any] = {}
    default_value: str | None = ""

    @model_validator(mode="before")
    @classmethod
    def validate_data(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize data structure."""
        if not isinstance(values, dict):
            raise ValueError("Data must be a dictionary")

        if "data" not in values or values["data"] is None:
            values["data"] = {}

        if not isinstance(values["data"], dict):
            raise ValueError("Data 'data' field must be a dictionary")

        # Move any extra fields into the data dict
        for key in list(values.keys()):
            if key not in {"text_key", "data", "default_value"}:
                if key not in values["data"]:
                    values["data"][key] = values.pop(key)

        return values

    def get_text(self) -> str:
        """Get the text value from the data dictionary."""
        return self.data.get(self.text_key, self.default_value or "")

    def set_text(self, text: str | None) -> str:
        """Set the text value in the data dictionary."""
        new_text = "" if text is None else str(text)
        self.data[self.text_key] = new_text
        return new_text

    def __getattr__(self, key: str) -> Any:
        """Allow attribute-like access to the data dictionary."""
        if key.startswith("__") or key in {"data", "text_key", "default_value"}:
            return super().__getattribute__(key)
        try:
            return self.data[key]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{key}'")

    def __setattr__(self, key: str, value: Any) -> None:
        """Set attribute-like values in the data dictionary."""
        if key in {"data", "text_key", "default_value"} or key.startswith("_"):
            super().__setattr__(key, value)
        elif key in self.model_fields:
            self.data[key] = value
            super().__setattr__(key, value)
        else:
            self.data[key] = value

    def __repr__(self) -> str:
        """Return string representation."""
        return f"Data(text_key={self.text_key!r}, data={self.data!r})"

