"""Telegram components for dfx framework."""

from .telegram_message import DFXTelegramMessageComponent

# Alias for backward compatibility
DFXTelegramComponent = DFXTelegramMessageComponent

__all__ = ["DFXTelegramMessageComponent", "DFXTelegramComponent"]