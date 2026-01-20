"""
Screen monitoring module for Gavin AI.

Provides window title and browser URL detection to identify
distracting websites and applications during focus sessions.
"""

from screen.window_detector import (
    WindowDetector,
    get_screen_state,
    get_screen_state_with_ai_fallback,
)
from screen.blocklist import Blocklist, BlocklistManager

__all__ = [
    "WindowDetector",
    "get_screen_state",
    "get_screen_state_with_ai_fallback",
    "Blocklist",
    "BlocklistManager",
]
