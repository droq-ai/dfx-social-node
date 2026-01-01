"""Social components for dfx framework."""

from .telegram.telegram_message import DFXTelegramMessageComponent
from .x.twitter_posts import DFXTwitterPostsComponent
from .reddit.reddit_posts import DFXRedditPostsComponent

__all__ = [
    "DFXTelegramMessageComponent",
    "DFXTwitterPostsComponent",
    "DFXRedditPostsComponent"
]