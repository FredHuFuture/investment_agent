"""Notification dispatchers for investment alerts."""
from notifications.email_dispatcher import EmailConfig, EmailDispatcher
from notifications.telegram_dispatcher import TelegramDispatcher

__all__ = ["EmailConfig", "EmailDispatcher", "TelegramDispatcher"]
