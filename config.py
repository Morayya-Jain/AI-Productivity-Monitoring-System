"""Configuration settings for Gavin AI."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_VISION_MODEL = "gpt-4o-mini"  # For image analysis (person/gadget detection)

# Camera Configuration
CAMERA_INDEX = 0
CAMERA_WIDE_MODE = True  # Enable wider 16:9 aspect ratio for more desk coverage

# Wide mode resolutions to try (in order of preference)
# These are 16:9 aspect ratio for maximum horizontal coverage
CAMERA_WIDE_RESOLUTIONS = [
    (1280, 720),   # 720p - good balance of quality and performance
    (1920, 1080),  # 1080p - higher quality (more API cost)
    (854, 480),    # Wide 480p fallback
]

# Default resolution (used if wide mode disabled or as fallback)
FRAME_WIDTH = 1280
FRAME_HEIGHT = 720
DETECTION_FPS = 0.33  # Frames per second to analyse

# Paths
DATA_DIR = BASE_DIR / "data" / "sessions"
# Save reports directly to user's Downloads folder
REPORTS_DIR = Path.home() / "Downloads"

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
# Downloads folder always exists, no need to create it

# Event types
EVENT_PRESENT = "present"
EVENT_AWAY = "away"
EVENT_GADGET_SUSPECTED = "gadget_suspected"
EVENT_PAUSED = "paused"  # User manually paused the session
EVENT_SCREEN_DISTRACTION = "screen_distraction"  # Distracting website/app detected

# Monitoring modes
MODE_CAMERA_ONLY = "camera_only"  # Default - only camera monitoring
MODE_SCREEN_ONLY = "screen_only"  # Only screen monitoring (no camera)
MODE_BOTH = "both"  # Camera + screen monitoring

# Screen monitoring settings
SCREEN_CHECK_INTERVAL = 3  # Seconds between screen checks (cheaper than camera)
SCREEN_SETTINGS_FILE = BASE_DIR / "data" / "blocklist.json"  # Blocklist persistence
SCREEN_AI_FALLBACK_ENABLED = False  # Enable AI Vision fallback (costs ~$0.001-0.002 per check)

# Unfocused alert settings
# Alert plays at each of these thresholds (in seconds) when user is unfocused
# After all alerts play, no more until user refocuses
UNFOCUSED_ALERT_TIMES = [20, 60, 120]  # Escalating alerts: 20s, 1min, 2min

# Supportive, non-condemning messages for each alert level
# Each tuple: (badge_text, main_message)
UNFOCUSED_ALERT_MESSAGES = [
    ("Focus paused", "We noticed you stepped away!"),           # 20s - gentle notice
    ("Quick check-in", "We are waiting for you :)"),       # 1min - reassuring
    ("Reminder", "Don't forget to come back ;)"),  # 2min - supportive
]

# How long the alert popup stays visible (seconds)
ALERT_POPUP_DURATION = 10

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # Can override in .env: DEBUG, INFO, WARNING, ERROR
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# MVP Usage Limit Settings
# Limits total usage time for trial/demo purposes
MVP_LIMIT_SECONDS = 7200  # Initial time limit in seconds (default: 2 hours)
MVP_EXTENSION_SECONDS = 7200  # Time added per password unlock in seconds (default: 2 hours)
MVP_UNLOCK_PASSWORD = os.getenv("MVP_UNLOCK_PASSWORD", "")  # Password to unlock more time
USAGE_DATA_FILE = BASE_DIR / "data" / "usage_data.json"
