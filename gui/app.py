"""
Gavin AI - Desktop GUI Application

A minimal tkinter GUI that wraps the existing detection code,
providing a user-friendly interface for focus session tracking.
"""

import tkinter as tk
from tkinter import messagebox, font as tkfont
import threading
import time
import logging
import subprocess
import sys
import os
from pathlib import Path
from typing import Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from camera.capture import CameraCapture
from camera.vision_detector import VisionDetector
from camera import get_event_type
from tracking.session import Session
from tracking.analytics import compute_statistics
from tracking.usage_limiter import get_usage_limiter, UsageLimiter
from reporting.pdf_report import generate_report
from instance_lock import check_single_instance, get_existing_pid
from screen.window_detector import WindowDetector, get_screen_state, get_screen_state_with_ai_fallback
from screen.blocklist import Blocklist, BlocklistManager, PRESET_CATEGORIES

logger = logging.getLogger(__name__)

# --- Color Palette ---
# Soft slate blue theme with warm accents
COLORS = {
    "bg_dark": "#1E293B",           # Soft slate blue background
    "bg_medium": "#334155",         # Card/panel background
    "bg_light": "#475569",          # Lighter panel elements
    "accent_primary": "#38BDF8",    # Sky blue accent
    "accent_warm": "#FB923C",       # Warm orange for alerts
    "text_primary": "#F1F5F9",      # Off-white text
    "text_secondary": "#94A3B8",    # Muted text
    "text_white": "#FFFFFF",        # Pure white for buttons
    "status_focused": "#4ADE80",    # Green for focused
    "status_away": "#FBBF24",       # Amber for away
    "status_gadget": "#F87171",     # Red for gadget distraction
    "status_screen": "#A78BFA",     # Purple for screen distraction
    "status_idle": "#64748B",       # Gray for idle
    "status_paused": "#94A3B8",     # Muted gray for paused
    "button_start": "#22C55E",      # Green start button
    "button_start_hover": "#16A34A", # Darker green on hover
    "button_stop": "#EF4444",       # Red stop button
    "button_stop_hover": "#DC2626", # Darker red on hover
    "button_pause": "#64748B",      # Grey pause button
    "button_pause_hover": "#475569", # Darker grey on hover
    "button_resume": "#38BDF8",     # Sky blue resume button (same as unlock)
    "button_resume_hover": "#0EA5E9", # Darker sky blue on hover
    "button_settings": "#6366F1",   # Indigo for settings button
    "button_settings_hover": "#4F46E5", # Darker indigo on hover
    "time_badge": "#8B5CF6",        # Purple for time remaining badge
    "time_badge_low": "#F97316",    # Orange when time is low
    "time_badge_expired": "#EF4444", # Red when time expired
    "toggle_on": "#6366F1",         # Indigo for enabled toggles (different from green Start button)
    "toggle_off": "#475569",        # Gray for disabled toggles
}

# Privacy settings file
PRIVACY_FILE = Path(__file__).parent.parent / "data" / ".privacy_accepted"

# Base dimensions for scaling
BASE_WIDTH = 520
BASE_HEIGHT = 520
MIN_WIDTH = 420
MIN_HEIGHT = 420


class RoundedFrame(tk.Canvas):
    """
    A frame with rounded corners using Canvas.
    
    Draws a rounded rectangle background and allows placing widgets inside.
    """
    
    def __init__(self, parent, bg_color: str, corner_radius: int = 15, **kwargs):
        """
        Initialize rounded frame.
        
        Args:
            parent: Parent widget
            bg_color: Background color for the rounded rectangle
            corner_radius: Radius of the corners
        """
        # Get parent background for canvas
        parent_bg = parent.cget("bg") if hasattr(parent, "cget") else COLORS["bg_dark"]
        
        super().__init__(parent, highlightthickness=0, bg=parent_bg, **kwargs)
        
        self.bg_color = bg_color
        self.corner_radius = corner_radius
        self._rect_id = None
        
        # Bind resize to redraw
        self.bind("<Configure>", self._on_resize)
    
    def _on_resize(self, event=None):
        """Redraw the rounded rectangle on resize."""
        self.delete("rounded_bg")
        
        width = self.winfo_width()
        height = self.winfo_height()
        
        if width > 1 and height > 1:
            self._draw_rounded_rect(0, 0, width, height, self.corner_radius, self.bg_color)
    
    def _draw_rounded_rect(self, x1, y1, x2, y2, radius, color):
        """
        Draw a rounded rectangle.
        
        Args:
            x1, y1: Top-left corner
            x2, y2: Bottom-right corner
            radius: Corner radius
            color: Fill color
        """
        # Ensure radius isn't larger than half the smallest dimension
        radius = min(radius, (x2 - x1) // 2, (y2 - y1) // 2)
        
        # Draw using polygon with smooth curves
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        
        self._rect_id = self.create_polygon(
            points, 
            fill=color, 
            smooth=True, 
            tags="rounded_bg"
        )
        
        # Send to back so widgets appear on top
        self.tag_lower("rounded_bg")


class RoundedButton(tk.Canvas):
    """
    A button with rounded corners.
    """
    
    def __init__(
        self, 
        parent, 
        text: str,
        command,
        bg_color: str,
        hover_color: str,
        fg_color: str = "#FFFFFF",
        font: tkfont.Font = None,
        corner_radius: int = 12,
        padx: int = 30,
        pady: int = 12,
        **kwargs
    ):
        """
        Initialize rounded button.
        
        Args:
            parent: Parent widget
            text: Button text
            command: Click callback
            bg_color: Background color
            hover_color: Color on hover
            fg_color: Text color
            font: Text font
            corner_radius: Corner radius
            padx, pady: Internal padding
        """
        self.text = text
        self.command = command
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.fg_color = fg_color
        self.btn_font = font
        self.corner_radius = corner_radius
        self.padx = padx
        self.pady = pady
        self._enabled = True
        
        # Get parent background
        parent_bg = parent.cget("bg") if hasattr(parent, "cget") else COLORS["bg_dark"]
        
        super().__init__(parent, highlightthickness=0, bg=parent_bg, **kwargs)
        
        # Bind events
        self.bind("<Configure>", self._on_resize)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        
        self._current_bg = bg_color
    
    def _on_resize(self, event=None):
        """Redraw button on resize."""
        self._draw_button()
    
    def _draw_button(self):
        """Draw the button with current state."""
        self.delete("all")
        
        width = self.winfo_width()
        height = self.winfo_height()
        
        if width > 1 and height > 1:
            # Draw rounded rectangle background
            radius = min(self.corner_radius, width // 4, height // 2)
            
            points = [
                radius, 0,
                width - radius, 0,
                width, 0,
                width, radius,
                width, height - radius,
                width, height,
                width - radius, height,
                radius, height,
                0, height,
                0, height - radius,
                0, radius,
                0, 0,
            ]
            
            self.create_polygon(
                points,
                fill=self._current_bg,
                smooth=True,
                tags="bg"
            )
            
            # Draw text
            self.create_text(
                width // 2,
                height // 2,
                text=self.text,
                fill=self.fg_color,
                font=self.btn_font,
                tags="text"
            )
    
    def _on_enter(self, event):
        """Mouse enter - show hover state."""
        if self._enabled:
            self._current_bg = self.hover_color
            self._draw_button()
            self.config(cursor="")  # Normal cursor
    
    def _on_leave(self, event):
        """Mouse leave - restore normal state."""
        if self._enabled:
            self._current_bg = self.bg_color
            self._draw_button()
    
    def _on_click(self, event):
        """Handle click."""
        if self._enabled and self.command:
            self.command()
    
    def configure_button(self, **kwargs):
        """
        Configure button properties.
        
        Args:
            text: New button text
            bg_color: New background color
            hover_color: New hover color
            state: tk.NORMAL or tk.DISABLED
        """
        if "text" in kwargs:
            self.text = kwargs["text"]
        if "bg_color" in kwargs:
            self.bg_color = kwargs["bg_color"]
            self._current_bg = kwargs["bg_color"]
        if "hover_color" in kwargs:
            self.hover_color = kwargs["hover_color"]
        if "state" in kwargs:
            self._enabled = (kwargs["state"] != tk.DISABLED)
            if not self._enabled:
                self._current_bg = COLORS["bg_light"]
            else:
                self._current_bg = self.bg_color
        
        self._draw_button()


class NotificationPopup:
    """
    A floating notification popup that appears on top of all windows.
    
    Shows supportive messages when the user is unfocused, with auto-dismiss
    after a configurable duration and a manual close button.
    """
    
    # Class-level reference to track active popup (only one at a time)
    _active_popup: Optional['NotificationPopup'] = None
    
    # Consistent font family for the app
    FONT_FAMILY = "SF Pro Display"
    FONT_FAMILY_FALLBACK = "Helvetica Neue"
    
    def __init__(
        self, 
        parent: tk.Tk, 
        badge_text: str,
        message: str, 
        duration_seconds: int = 10
    ):
        """
        Initialize the notification popup.
        
        Args:
            parent: Parent Tk root window
            badge_text: The badge/pill text (e.g., "Focus paused")
            message: The main message to display
            duration_seconds: How long before auto-dismiss (default 10s)
        """
        # Dismiss any existing popup first
        if NotificationPopup._active_popup is not None:
            NotificationPopup._active_popup.dismiss()
        
        self.parent = parent
        self.badge_text = badge_text
        self.message = message
        self.duration = duration_seconds
        self._dismiss_after_id: Optional[str] = None
        self._is_dismissed = False
        
        # Create the popup window
        self.window = tk.Toplevel(parent)
        self.window.overrideredirect(True)  # Borderless window
        self.window.attributes('-topmost', True)  # Always on top
        
        # Popup dimensions (compact card)
        self.popup_width = 280
        self.popup_height = 200
        
        # On macOS, make the window background transparent for true rounded corners
        if sys.platform == "darwin":
            # Use transparent background
            self.window.attributes('-transparent', True)
            self.window.config(bg='systemTransparent')
        
        # Center on screen
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = (screen_width - self.popup_width) // 2
        y = (screen_height - self.popup_height) // 2
        self.window.geometry(f"{self.popup_width}x{self.popup_height}+{x}+{y}")
        
        # Build the UI
        self._create_ui()
        
        # Start auto-dismiss timer
        self._start_dismiss_timer()
        
        # Register as active popup
        NotificationPopup._active_popup = self
        
        # Aggressively bring notification to front (even when app is in background)
        self._ensure_front()
        
        logger.debug(f"Notification popup shown: {badge_text} - {message}")
    
    def _ensure_front(self):
        """Ensure the notification stays on top of all windows."""
        if self._is_dismissed:
            return
        
        # Lift and focus
        self.window.lift()
        self.window.attributes('-topmost', True)
        
        # On macOS, we need to be more aggressive
        if sys.platform == "darwin":
            self.window.focus_force()
            # Schedule additional lifts to ensure visibility
            self.parent.after(50, self._lift_again)
            self.parent.after(150, self._lift_again)
            self.parent.after(300, self._lift_again)
    
    def _lift_again(self):
        """Lift the window again (called after delays)."""
        if self._is_dismissed:
            return
        try:
            self.window.lift()
            self.window.attributes('-topmost', True)
        except Exception:
            pass
    
    def _get_font(self, size: int, weight: str = "normal") -> tuple:
        """Get font tuple with fallback."""
        return (self.FONT_FAMILY, size, weight)
    
    def _create_ui(self):
        """Build the popup UI matching the reference design."""
        # Colors matching the design exactly
        bg_color = "#FFFFFF"           # White background
        text_dark = "#1F2937"          # Dark text for message
        text_muted = "#B0B8C1"         # Light gray for close button
        accent_blue = "#818CF8"        # Blue color for GAVIN AI title (matching image)
        badge_bg = "#F3F4F6"           # Light gray badge background
        badge_border = "#E5E7EB"       # Badge border
        badge_text_color = "#4B5563"   # Dark gray badge text
        dot_color = "#D1D5DB"          # Very light gray dot (subtle)
        corner_radius = 24             # Rounded corners
        
        # Transparent background for macOS, white for others
        if sys.platform == "darwin":
            canvas_bg = 'systemTransparent'
        else:
            canvas_bg = bg_color
        
        # Create canvas for the popup
        self.canvas = tk.Canvas(
            self.window,
            width=self.popup_width,
            height=self.popup_height,
            bg=canvas_bg,
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Draw main white background with rounded corners
        self._draw_smooth_rounded_rect(
            self.canvas,
            0, 0,
            self.popup_width, self.popup_height,
            corner_radius,
            fill=bg_color
        )
        
        # "GAVIN AI" title
        title_y = 32
        title_x = 28
        self.canvas.create_text(
            title_x, title_y,
            text="GAVIN AI",
            font=self._get_font(14, "bold"),
            fill=accent_blue,
            anchor="w"
        )
        
        # Status dot right next to title (very close)
        dot_x = title_x + 72  # Right next to text
        dot_size = 7
        self.canvas.create_oval(
            dot_x, title_y - dot_size // 2,
            dot_x + dot_size, title_y + dot_size // 2,
            fill=dot_color,
            outline=""
        )
        
        # Close button with hover background
        close_x = self.popup_width - 32
        close_y = title_y
        close_bg_color = "#F0F4F5"  # Light gray background on hover (RGB 240, 244, 245)
        
        # Background circle for close button (starts as white/invisible, needs fill for events)
        self.close_bg_id = self.canvas.create_oval(
            close_x - 16, close_y - 16,
            close_x + 16, close_y + 16,
            fill=bg_color,  # Same as background (white) so it's invisible but receives events
            outline="",
            tags="close_btn"
        )
        
        # Close button "X"
        self.close_text_id = self.canvas.create_text(
            close_x, close_y,
            text="\u00D7",  # Multiplication sign (cleaner X)
            font=self._get_font(28, "normal"),
            fill=text_muted,
            anchor="center",
            tags="close_btn"
        )
        
        # Store colors for hover events
        self._close_bg_color = close_bg_color
        self._close_bg_normal = bg_color  # White background when not hovering
        self._text_muted = text_muted
        self._text_dark = text_dark
        
        # Bind close button events with background highlight
        self.canvas.tag_bind("close_btn", "<Button-1>", lambda e: self.dismiss())
        self.canvas.tag_bind("close_btn", "<Enter>", self._on_close_hover_enter)
        self.canvas.tag_bind("close_btn", "<Leave>", self._on_close_hover_leave)
        
        # Badge/pill below title
        badge_y = 68
        badge_padding_x = 14
        
        # Measure badge text width (approximate)
        badge_char_width = 7.5
        badge_width = len(self.badge_text) * badge_char_width + badge_padding_x * 2
        badge_height = 28
        
        # Draw badge background (rounded pill)
        self._draw_smooth_rounded_rect(
            self.canvas,
            28, badge_y - badge_height // 2,
            28 + badge_width, badge_y + badge_height // 2,
            badge_height // 2,
            fill=badge_bg,
            outline=badge_border
        )
        
        # Badge text
        self.canvas.create_text(
            28 + badge_width // 2, badge_y,
            text=self.badge_text,
            font=self._get_font(12, "normal"),
            fill=badge_text_color,
            anchor="center"
        )
        
        # Main message text (large, left-aligned)
        message_y = 105
        self.canvas.create_text(
            28, message_y,
            text=self.message,
            font=self._get_font(22, "normal"),
            fill=text_dark,
            anchor="nw",
            width=self.popup_width - 56
        )
    
    def _on_close_hover_enter(self, event):
        """Show gray background on close button hover."""
        self.canvas.itemconfig(self.close_bg_id, fill=self._close_bg_color)
        self.canvas.itemconfig(self.close_text_id, fill=self._text_dark)
    
    def _on_close_hover_leave(self, event):
        """Hide gray background when leaving close button."""
        self.canvas.itemconfig(self.close_bg_id, fill=self._close_bg_normal)
        self.canvas.itemconfig(self.close_text_id, fill=self._text_muted)
    
    def _draw_smooth_rounded_rect(self, canvas, x1, y1, x2, y2, radius, fill="white", outline=""):
        """
        Draw a properly rounded rectangle using arcs for smooth corners.
        
        Args:
            canvas: The canvas to draw on
            x1, y1: Top-left corner
            x2, y2: Bottom-right corner
            radius: Corner radius
            fill: Fill color
            outline: Outline color
        """
        # Draw the rounded rectangle using multiple shapes
        # Top edge
        canvas.create_rectangle(x1 + radius, y1, x2 - radius, y1 + radius, fill=fill, outline="")
        # Bottom edge
        canvas.create_rectangle(x1 + radius, y2 - radius, x2 - radius, y2, fill=fill, outline="")
        # Left edge
        canvas.create_rectangle(x1, y1 + radius, x1 + radius, y2 - radius, fill=fill, outline="")
        # Right edge
        canvas.create_rectangle(x2 - radius, y1 + radius, x2, y2 - radius, fill=fill, outline="")
        # Center
        canvas.create_rectangle(x1 + radius, y1 + radius, x2 - radius, y2 - radius, fill=fill, outline="")
        
        # Draw corner arcs (circles clipped to quarters)
        # Top-left corner
        canvas.create_arc(x1, y1, x1 + radius * 2, y1 + radius * 2, 
                         start=90, extent=90, fill=fill, outline="")
        # Top-right corner
        canvas.create_arc(x2 - radius * 2, y1, x2, y1 + radius * 2, 
                         start=0, extent=90, fill=fill, outline="")
        # Bottom-left corner
        canvas.create_arc(x1, y2 - radius * 2, x1 + radius * 2, y2, 
                         start=180, extent=90, fill=fill, outline="")
        # Bottom-right corner
        canvas.create_arc(x2 - radius * 2, y2 - radius * 2, x2, y2, 
                         start=270, extent=90, fill=fill, outline="")
    
    
    def _start_dismiss_timer(self):
        """Start the auto-dismiss countdown."""
        duration_ms = self.duration * 1000
        self._dismiss_after_id = self.parent.after(duration_ms, self.dismiss)
    
    def dismiss(self):
        """Close and destroy the popup."""
        if self._is_dismissed:
            return
        
        self._is_dismissed = True
        
        # Cancel pending auto-dismiss timer
        if self._dismiss_after_id:
            try:
                self.parent.after_cancel(self._dismiss_after_id)
            except Exception:
                pass
        
        # Destroy window
        try:
            self.window.destroy()
        except Exception:
            pass
        
        # Clear active popup reference
        if NotificationPopup._active_popup is self:
            NotificationPopup._active_popup = None
        
        logger.debug("Notification popup dismissed")


class GavinGUI:
    """
    Main GUI application for Gavin AI focus tracker.
    
    Provides a clean, scalable interface with:
    - Start/Stop session button
    - Status indicator (Focused / Away / On another gadget)
    - Session timer
    - Auto-generates PDF report on session stop
    """
    
    def __init__(self):
        """Initialize the GUI application."""
        self.root = tk.Tk()
        self.root.title("")  # Empty title - no text in title bar
        self.root.configure(bg=COLORS["bg_dark"])
        
        # Window size and positioning - center on screen
        # Update to ensure accurate screen dimensions
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - BASE_WIDTH) // 2
        y = (screen_height - BASE_HEIGHT) // 2
        self.root.geometry(f"{BASE_WIDTH}x{BASE_HEIGHT}+{x}+{y}")
        
        # Enable resizing with minimum size
        self.root.resizable(True, True)
        self.root.minsize(MIN_WIDTH, MIN_HEIGHT)
        
        # Track current scale for font adjustments
        self.current_scale = 1.0
        self._last_width = BASE_WIDTH
        self._last_height = BASE_HEIGHT
        
        # State variables
        self.session: Optional[Session] = None
        self.is_running = False
        self.should_stop = threading.Event()
        self.detection_thread: Optional[threading.Thread] = None
        self.screen_detection_thread: Optional[threading.Thread] = None
        self.current_status = "idle"  # idle, focused, away, gadget, screen, paused
        self.session_start_time: Optional[datetime] = None
        self.session_started = False  # Track if first detection has occurred
        
        # Monitoring mode (defaults to camera-only for backward compatibility)
        self.monitoring_mode = config.MODE_CAMERA_ONLY
        self.blocklist_manager = BlocklistManager(config.SCREEN_SETTINGS_FILE)
        self.blocklist = self.blocklist_manager.load()
        self.use_ai_fallback = config.SCREEN_AI_FALLBACK_ENABLED
        
        # Pause state tracking
        self.is_paused = False  # Whether session is currently paused
        self.pause_start_time: Optional[datetime] = None  # When current pause began
        self.total_paused_seconds: float = 0.0  # Accumulated pause time in session (float for precision)
        self.frozen_active_seconds: int = 0  # Frozen timer display value when paused
        
        # Unfocused alert tracking
        self.unfocused_start_time: Optional[float] = None
        self.alerts_played: int = 0  # Tracks how many alerts have been played (max 3)
        
        # Usage limit tracking
        self.usage_limiter: UsageLimiter = get_usage_limiter()
        self.is_locked: bool = False  # True when time exhausted and app is locked
        
        # UI update lock
        self.ui_lock = threading.Lock()
        
        # Create UI elements
        self._create_fonts()
        self._create_widgets()
        
        # Bind resize event for scaling
        self.root.bind("<Configure>", self._on_resize)
        
        # Bind Enter key to start/stop session
        self.root.bind("<Return>", self._on_enter_key)
        
        # Check privacy acceptance
        self.root.after(100, self._check_privacy)
        
        # Check usage limit status
        self.root.after(200, self._check_usage_limit)
        
        # Update timer periodically
        self._update_timer()
        
        # Update usage display periodically
        self._update_usage_display()
        
        # Handle window close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Bring window to front on launch (no special permissions needed)
        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after(100, lambda: self.root.attributes('-topmost', False))
        self.root.focus_force()
    
    def _create_fonts(self):
        """Create custom fonts for the UI with fixed sizes."""
        # Use SF Pro Display for consistent modern look (fallback to Helvetica Neue)
        font_family = "SF Pro Display"
        font_family_mono = "SF Mono"
        
        self.font_title = tkfont.Font(
            family=font_family, size=26, weight="bold"
        )
        
        self.font_timer = tkfont.Font(
            family=font_family_mono, size=36, weight="bold"
        )
        
        self.font_status = tkfont.Font(
            family=font_family, size=15, weight="normal"
        )
        
        self.font_button = tkfont.Font(
            family=font_family, size=14, weight="bold"
        )
        
        self.font_small = tkfont.Font(
            family=font_family, size=11, weight="normal"
        )
        
        self.font_badge = tkfont.Font(
            family=font_family, size=10, weight="bold"
        )
    
    
    def _on_resize(self, event):
        """
        Handle window resize event - scale UI components proportionally.
        
        Note: Font sizes stay fixed. Only buttons and containers scale.
        
        Args:
            event: Configure event with new dimensions
        """
        # Only respond to root window resize
        if event.widget != self.root:
            return
        
        # Check if size actually changed
        if event.width == self._last_width and event.height == self._last_height:
            return
        
        self._last_width = event.width
        self._last_height = event.height
        
        # Calculate scale based on both dimensions
        width_scale = event.width / BASE_WIDTH
        height_scale = event.height / BASE_HEIGHT
        new_scale = min(width_scale, height_scale)
        
        # Update if scale changed significantly
        if abs(new_scale - self.current_scale) > 0.05:
            self.current_scale = new_scale
            
            # Scale button proportionally (but keep minimum size)
            if hasattr(self, 'start_stop_btn'):
                new_btn_width = max(160, int(180 * new_scale))
                new_btn_height = max(46, int(52 * new_scale))
                self.start_stop_btn.configure(width=new_btn_width, height=new_btn_height)
                self.start_stop_btn._draw_button()
            
            # Scale status card height proportionally
            if hasattr(self, 'status_card'):
                new_card_height = max(50, int(60 * new_scale))
                self.status_card.configure(height=new_card_height)
    
    def _get_current_status_color(self) -> str:
        """Get the color for the current status."""
        color_map = {
            "idle": COLORS["status_idle"],
            "focused": COLORS["status_focused"],
            "away": COLORS["status_away"],
            "gadget": COLORS["status_gadget"],
            "screen": COLORS["status_screen"],
            "paused": COLORS["status_paused"],
        }
        return color_map.get(self.current_status, COLORS["status_idle"])
    
    def _create_widgets(self):
        """Create all UI widgets with scalable layout."""
        # Main container using grid for proportional spacing
        self.main_frame = tk.Frame(self.root, bg=COLORS["bg_dark"])
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=25, pady=20)
        
        # Configure grid rows with weights for proportional expansion
        # Row 0: Spacer (expands)
        # Row 1: Title (fixed)
        # Row 2: Spacer (expands)
        # Row 3: Status card (fixed)
        # Row 4: Spacer (expands more)
        # Row 5: Timer (fixed)
        # Row 6: Spacer (expands more)
        # Row 7: Button (fixed)
        # Row 8: Spacer (expands)
        
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)   # Top spacer
        self.main_frame.grid_rowconfigure(1, weight=0)   # Title
        self.main_frame.grid_rowconfigure(2, weight=1)   # Spacer
        self.main_frame.grid_rowconfigure(8, weight=0)   # Mode selector (added)
        self.main_frame.grid_rowconfigure(3, weight=0)   # Status
        self.main_frame.grid_rowconfigure(4, weight=2)   # Spacer (more weight)
        self.main_frame.grid_rowconfigure(5, weight=0)   # Timer
        self.main_frame.grid_rowconfigure(6, weight=2)   # Spacer (more weight)
        self.main_frame.grid_rowconfigure(7, weight=0)   # Button
        self.main_frame.grid_rowconfigure(8, weight=1)   # Bottom spacer
        
        # --- Title Section ---
        title_frame = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        title_frame.grid(row=1, column=0, sticky="ew")
        
        self.title_label = tk.Label(
            title_frame,
            text="GAVIN AI",
            font=self.font_title,
            fg=COLORS["accent_primary"],
            bg=COLORS["bg_dark"]
        )
        self.title_label.pack()
        
        self.subtitle_label = tk.Label(
            title_frame,
            text="Focus Tracker",
            font=self.font_small,
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_dark"]
        )
        self.subtitle_label.pack()
        
        # --- Time Remaining Badge (clickable for details) ---
        self.time_badge_frame = tk.Frame(title_frame, bg=COLORS["bg_dark"])
        self.time_badge_frame.pack(pady=(10, 0))
        
        self.time_badge = tk.Label(
            self.time_badge_frame,
            text="2h 0m left",
            font=self.font_badge,
            fg=COLORS["text_white"],
            bg=COLORS["time_badge"],
            padx=12,
            pady=4,
        )
        self.time_badge.pack()
        self.time_badge.bind("<Button-1>", self._show_usage_details)
        
        # Lockout overlay (hidden by default)
        self.lockout_frame: Optional[tk.Frame] = None
        
        # --- Status Card (Rounded) ---
        status_container = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        status_container.grid(row=3, column=0, sticky="ew", padx=10)
        
        self.status_card = RoundedFrame(
            status_container,
            bg_color=COLORS["bg_medium"],
            corner_radius=12,
            height=60
        )
        self.status_card.pack(fill=tk.X)
        
        # Status content frame (inside the rounded card)
        self.status_content = tk.Frame(self.status_card, bg=COLORS["bg_medium"])
        self.status_content.place(relx=0.5, rely=0.5, anchor="center")
        
        # Status dot (using canvas for round shape)
        self.status_dot = tk.Canvas(
            self.status_content,
            width=14,
            height=14,
            bg=COLORS["bg_medium"],
            highlightthickness=0
        )
        self.status_dot.pack(side=tk.LEFT, padx=(0, 10))
        self._draw_status_dot(COLORS["status_idle"])
        
        self.status_label = tk.Label(
            self.status_content,
            text="Ready to Start",
            font=self.font_status,
            fg=COLORS["text_primary"],
            bg=COLORS["bg_medium"]
        )
        self.status_label.pack(side=tk.LEFT)
        
        # --- Timer Display ---
        timer_frame = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        timer_frame.grid(row=5, column=0, sticky="ew")
        
        self.timer_label = tk.Label(
            timer_frame,
            text="00:00:00",
            font=self.font_timer,
            fg=COLORS["text_primary"],
            bg=COLORS["bg_dark"]
        )
        self.timer_label.pack()
        
        self.timer_sub_label = tk.Label(
            timer_frame,
            text="Session Duration",
            font=self.font_small,
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_dark"]
        )
        self.timer_sub_label.pack(pady=(5, 0))
        
        # --- Button Section ---
        button_frame = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        button_frame.grid(row=7, column=0, sticky="ew")
        
        # Pause/Resume Button (Rounded) - hidden initially, appears when session running
        self.pause_btn = RoundedButton(
            button_frame,
            text="Pause Session",
            command=self._toggle_pause,
            bg_color=COLORS["button_pause"],
            hover_color=COLORS["button_pause_hover"],
            fg_color=COLORS["text_white"],
            font=self.font_button,
            corner_radius=10,
            width=180,
            height=52
        )
        # Hidden initially - will be shown when session starts
        
        # Start/Stop Button (Rounded) - centered
        self.start_stop_btn = RoundedButton(
            button_frame,
            text="Start Session",
            command=self._toggle_session,
            bg_color=COLORS["button_start"],
            hover_color=COLORS["button_start_hover"],
            fg_color=COLORS["text_white"],
            font=self.font_button,
            corner_radius=10,
            width=180,
            height=52
        )
        self.start_stop_btn.pack()
        
        # --- Mode Selector Section (below buttons) ---
        self._create_mode_selector()
    
    def _create_mode_selector(self):
        """
        Create the monitoring mode selector UI.
        
        Allows users to choose between Camera Only, Screen Only, or Both modes.
        Also provides access to blocklist settings.
        """
        # Mode selector container
        self.mode_frame = tk.Frame(self.main_frame, bg=COLORS["bg_dark"])
        self.mode_frame.grid(row=8, column=0, sticky="ew", pady=(15, 0))
        
        # Mode label
        mode_label = tk.Label(
            self.mode_frame,
            text="Monitoring Mode",
            font=self.font_small,
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_dark"]
        )
        mode_label.pack()
        
        # Mode buttons container
        mode_buttons_frame = tk.Frame(self.mode_frame, bg=COLORS["bg_dark"])
        mode_buttons_frame.pack(pady=(5, 0))
        
        # Create mode toggle buttons
        self.mode_var = tk.StringVar(value=config.MODE_CAMERA_ONLY)
        
        modes = [
            (config.MODE_CAMERA_ONLY, "📷 Camera"),
            (config.MODE_SCREEN_ONLY, "🖥 Screen"),
            (config.MODE_BOTH, "📷+🖥 Both"),
        ]
        
        self.mode_buttons = {}
        for mode_id, mode_text in modes:
            btn = tk.Label(
                mode_buttons_frame,
                text=mode_text,
                font=self.font_small,
                fg=COLORS["text_white"] if mode_id == self.monitoring_mode else COLORS["text_secondary"],
                bg=COLORS["toggle_on"] if mode_id == self.monitoring_mode else COLORS["toggle_off"],
                padx=12,
                pady=6,
            )
            btn.pack(side=tk.LEFT, padx=2)
            btn.bind("<Button-1>", lambda e, m=mode_id: self._set_monitoring_mode(m))
            self.mode_buttons[mode_id] = btn
        
        # Settings button (for blocklist management)
        settings_frame = tk.Frame(self.mode_frame, bg=COLORS["bg_dark"])
        settings_frame.pack(pady=(8, 0))
        
        self.settings_btn = tk.Label(
            settings_frame,
            text="⚙️ Blocklist Settings",
            font=self.font_small,
            fg=COLORS["accent_primary"],
            bg=COLORS["bg_dark"]
        )
        self.settings_btn.pack()
        self.settings_btn.bind("<Button-1>", lambda e: self._show_blocklist_settings())
        self.settings_btn.bind("<Enter>", lambda e: self.settings_btn.configure(fg=COLORS["accent_warm"]))
        self.settings_btn.bind("<Leave>", lambda e: self.settings_btn.configure(fg=COLORS["accent_primary"]))
    
    def _set_monitoring_mode(self, mode: str):
        """
        Set the monitoring mode.
        
        Args:
            mode: One of MODE_CAMERA_ONLY, MODE_SCREEN_ONLY, or MODE_BOTH
        """
        # Don't change mode while session is running
        if self.is_running:
            messagebox.showwarning(
                "Session Active",
                "Cannot change monitoring mode while a session is running.\n"
                "Please stop the current session first."
            )
            return
        
        self.monitoring_mode = mode
        self.mode_var.set(mode)
        
        # Update button visuals
        for mode_id, btn in self.mode_buttons.items():
            if mode_id == mode:
                btn.configure(
                    fg=COLORS["text_white"],
                    bg=COLORS["toggle_on"]
                )
            else:
                btn.configure(
                    fg=COLORS["text_secondary"],
                    bg=COLORS["toggle_off"]
                )
        
        logger.info(f"Monitoring mode set to: {mode}")
    
    def _show_blocklist_settings(self):
        """
        Show the blocklist settings dialog.
        
        Allows users to enable/disable preset categories and add custom patterns.
        """
        # Create settings window
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Blocklist Settings")
        settings_window.configure(bg=COLORS["bg_dark"])
        settings_window.geometry("400x580")
        settings_window.resizable(False, False)
        
        # Center on parent window
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        x = self.root.winfo_x() + (self.root.winfo_width() - 400) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 580) // 2
        settings_window.geometry(f"+{x}+{y}")
        
        # Main container with padding
        main_container = tk.Frame(settings_window, bg=COLORS["bg_dark"])
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Title
        title = tk.Label(
            main_container,
            text="Blocklist Settings",
            font=self.font_title,
            fg=COLORS["accent_primary"],
            bg=COLORS["bg_dark"]
        )
        title.pack()
        
        subtitle = tk.Label(
            main_container,
            text="Configure which sites/apps to block",
            font=self.font_small,
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_dark"]
        )
        subtitle.pack(pady=(5, 15))
        
        # Categories section
        categories_label = tk.Label(
            main_container,
            text="Preset Categories",
            font=self.font_status,
            fg=COLORS["text_primary"],
            bg=COLORS["bg_dark"]
        )
        categories_label.pack(anchor="w")
        
        # Category toggles
        self.category_vars = {}
        categories_frame = tk.Frame(main_container, bg=COLORS["bg_dark"])
        categories_frame.pack(fill=tk.X, pady=(5, 15))
        
        for cat_id, cat_data in PRESET_CATEGORIES.items():
            var = tk.BooleanVar(value=cat_id in self.blocklist.enabled_categories)
            self.category_vars[cat_id] = var
            
            row = tk.Frame(categories_frame, bg=COLORS["bg_dark"])
            row.pack(fill=tk.X, pady=2)
            
            cb = tk.Checkbutton(
                row,
                text=cat_data["name"],
                variable=var,
                font=self.font_small,
                fg=COLORS["text_primary"],
                bg=COLORS["bg_dark"],
                selectcolor=COLORS["bg_medium"],
                activebackground=COLORS["bg_dark"],
                activeforeground=COLORS["text_primary"],
                command=lambda c=cat_id, v=var: self._toggle_category(c, v.get())
            )
            cb.pack(side=tk.LEFT)
            
            # Clickable label to show sites in category
            desc = tk.Label(
                row,
                text=f"({len(cat_data['patterns'])} sites)",
                font=self.font_small,
                fg=COLORS["accent_primary"],
                bg=COLORS["bg_dark"]
            )
            desc.pack(side=tk.LEFT, padx=(5, 0))
            # Bind click to show sites popup
            desc.bind("<Button-1>", lambda e, c=cat_id, d=cat_data: self._show_category_sites(c, d))
            desc.bind("<Enter>", lambda e, lbl=desc: lbl.configure(fg=COLORS["accent_warm"]))
            desc.bind("<Leave>", lambda e, lbl=desc: lbl.configure(fg=COLORS["accent_primary"]))
        
        # Custom patterns section
        custom_label = tk.Label(
            main_container,
            text="Custom Patterns",
            font=self.font_status,
            fg=COLORS["text_primary"],
            bg=COLORS["bg_dark"]
        )
        custom_label.pack(anchor="w", pady=(10, 5))
        
        custom_help = tk.Label(
            main_container,
            text="Add URLs or app names to block (one per line)",
            font=self.font_small,
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_dark"]
        )
        custom_help.pack(anchor="w")
        
        # Custom patterns text area
        custom_frame = tk.Frame(main_container, bg=COLORS["bg_medium"])
        custom_frame.pack(fill=tk.X, pady=(5, 15))
        
        self.custom_text = tk.Text(
            custom_frame,
            font=self.font_small,
            fg=COLORS["text_primary"],
            bg=COLORS["bg_medium"],
            insertbackground=COLORS["text_primary"],
            height=5,
            wrap=tk.WORD
        )
        self.custom_text.pack(fill=tk.X, padx=5, pady=5)
        
        # Populate with current custom patterns
        if self.blocklist.custom_patterns:
            self.custom_text.insert("1.0", "\n".join(self.blocklist.custom_patterns))
        
        # AI Fallback option (advanced) - OFF BY DEFAULT
        ai_frame = tk.Frame(main_container, bg=COLORS["bg_dark"])
        ai_frame.pack(fill=tk.X, pady=(10, 15))
        
        self.ai_fallback_var = tk.BooleanVar(value=self.use_ai_fallback)
        ai_cb = tk.Checkbutton(
            ai_frame,
            text="Enable AI Screenshot Analysis (disabled by default)",
            variable=self.ai_fallback_var,
            font=self.font_small,
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_dark"],
            selectcolor=COLORS["bg_medium"],
            activebackground=COLORS["bg_dark"],
            activeforeground=COLORS["text_secondary"],
        )
        ai_cb.pack(anchor="w")
        
        ai_help = tk.Label(
            ai_frame,
            text="⚠️ Takes screenshots - only use if URL detection fails",
            font=self.font_small,
            fg=COLORS["accent_warm"],
            bg=COLORS["bg_dark"]
        )
        ai_help.pack(anchor="w", padx=(20, 0))
        
        # Buttons - centered at bottom
        button_frame = tk.Frame(main_container, bg=COLORS["bg_dark"])
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Center the buttons
        button_container = tk.Frame(button_frame, bg=COLORS["bg_dark"])
        button_container.pack()
        
        save_btn = RoundedButton(
            button_container,
            text="Save Settings",
            command=lambda: self._save_blocklist_settings(settings_window),
            bg_color=COLORS["button_start"],
            hover_color=COLORS["button_start_hover"],
            fg_color=COLORS["text_white"],
            font=self.font_button,
            corner_radius=8,
            width=150,
            height=44
        )
        save_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        cancel_btn = RoundedButton(
            button_container,
            text="Cancel",
            command=settings_window.destroy,
            bg_color=COLORS["button_pause"],
            hover_color=COLORS["button_pause_hover"],
            fg_color=COLORS["text_white"],
            font=self.font_button,
            corner_radius=8,
            width=100,
            height=44
        )
        cancel_btn.pack(side=tk.LEFT)
    
    def _toggle_category(self, category_id: str, enabled: bool):
        """
        Toggle a blocklist category on/off.
        
        Args:
            category_id: The category to toggle
            enabled: Whether to enable or disable
        """
        if enabled:
            self.blocklist.enable_category(category_id)
        else:
            self.blocklist.disable_category(category_id)
    
    def _show_category_sites(self, category_id: str, cat_data: dict):
        """
        Show a popup with the list of sites in a category.
        
        Args:
            category_id: The category ID
            cat_data: Category data dictionary with patterns
        """
        # Create a small popup window
        sites_popup = tk.Toplevel(self.root)
        sites_popup.title(f"{cat_data['name']} Sites")
        sites_popup.configure(bg="#1E293B")  # Dark background
        sites_popup.geometry("320x320")
        sites_popup.resizable(False, False)
        
        # Center on parent
        sites_popup.transient(self.root)
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 320) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 320) // 2
        sites_popup.geometry(f"+{x}+{y}")
        
        # Make modal to ensure proper event handling
        sites_popup.grab_set()
        sites_popup.focus_set()
        
        # Main container
        container = tk.Frame(sites_popup, bg="#1E293B")
        container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Title
        title = tk.Label(
            container,
            text=cat_data['name'],
            font=self.font_status,
            fg="#38BDF8",  # Sky blue
            bg="#1E293B"
        )
        title.pack()
        
        desc = tk.Label(
            container,
            text=cat_data.get('description', ''),
            font=self.font_small,
            fg="#94A3B8",  # Secondary text
            bg="#1E293B"
        )
        desc.pack(pady=(0, 10))
        
        # Sites list using a Listbox (better for dark themes)
        list_frame = tk.Frame(container, bg="#334155")
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        # Use Listbox instead of Text widget for better compatibility
        sites_listbox = tk.Listbox(
            list_frame,
            font=self.font_small,
            fg="#F1F5F9",  # Light text
            bg="#334155",  # Dark slate background
            selectbackground="#475569",
            selectforeground="#F1F5F9",
            highlightthickness=0,
            bd=0,
            relief=tk.FLAT
        )
        sites_listbox.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Insert all sites
        for pattern in cat_data['patterns']:
            sites_listbox.insert(tk.END, f"  • {pattern}")
        
        # Define close function
        def close_popup():
            sites_popup.grab_release()
            sites_popup.destroy()
        
        # Use RoundedButton for consistent styling with rounded corners
        close_btn = RoundedButton(
            container,
            text="Close",
            command=close_popup,
            bg_color="#475569",       # Dark slate grey
            hover_color="#64748B",    # Lighter slate on hover
            fg_color="#F1F5F9",       # Light text
            font=self.font_small,
            corner_radius=10,
            padx=24,
            pady=10
        )
        close_btn.pack(pady=(12, 0))
        # Set explicit size for RoundedButton
        close_btn.configure(width=80, height=36)
        
        # Also close on Escape key
        sites_popup.bind("<Escape>", lambda e: close_popup())
    
    def _validate_pattern(self, pattern: str) -> tuple:
        """
        Validate a custom blocklist pattern.
        
        Args:
            pattern: The pattern to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        import re
        pattern = pattern.strip().lower()
        
        # Must be at least 3 characters
        if len(pattern) < 3:
            return False, f"'{pattern}' is too short (min 3 characters)"
        
        # Should look like a domain or app name
        # Valid: letters, numbers, dots, hyphens, underscores, colons (for ://x.com style)
        if not re.match(r'^[:a-z0-9][a-z0-9._\-:/]*[a-z0-9]$', pattern):
            return False, f"'{pattern}' contains invalid characters"
        
        # Warn about overly generic single words that could cause false positives
        generic_terms = {'app', 'web', 'com', 'net', 'org', 'the', 'new', 'pro'}
        if pattern in generic_terms:
            return False, f"'{pattern}' is too generic and may cause false positives"
        
        # Check for patterns that are too short without a dot (likely incomplete)
        if len(pattern) <= 4 and '.' not in pattern:
            return False, f"'{pattern}' is too short - use full domain (e.g., {pattern}.com)"
        
        return True, ""
    
    def _save_blocklist_settings(self, settings_window: tk.Toplevel):
        """
        Save blocklist settings and close the dialog.
        Validates patterns and handles duplicates gracefully.
        
        Args:
            settings_window: The settings window to close
        """
        # Get custom patterns from text area
        custom_text = self.custom_text.get("1.0", tk.END).strip()
        raw_patterns = [p.strip().lower() for p in custom_text.split("\n") if p.strip()]
        
        # Validate each pattern
        valid_patterns = []
        invalid_patterns = []
        
        for pattern in raw_patterns:
            is_valid, error = self._validate_pattern(pattern)
            if is_valid:
                valid_patterns.append(pattern)
            else:
                invalid_patterns.append(error)
        
        # If there are invalid patterns, show error and don't save
        if invalid_patterns:
            error_msg = "Some patterns are invalid:\n\n" + "\n".join(invalid_patterns[:5])
            if len(invalid_patterns) > 5:
                error_msg += f"\n... and {len(invalid_patterns) - 5} more"
            error_msg += "\n\nPlease fix these and try again."
            messagebox.showerror("Invalid Patterns", error_msg)
            return  # Don't close dialog, let user fix
        
        # Remove duplicates within custom patterns (case-insensitive)
        seen = set()
        unique_patterns = []
        duplicates_removed = []
        
        for pattern in valid_patterns:
            if pattern not in seen:
                seen.add(pattern)
                unique_patterns.append(pattern)
            else:
                duplicates_removed.append(pattern)
        
        # Check for overlaps with preset categories
        preset_patterns = set()
        for cat_id in self.blocklist.enabled_categories:
            if cat_id in PRESET_CATEGORIES:
                for p in PRESET_CATEGORIES[cat_id]['patterns']:
                    preset_patterns.add(p.lower())
        
        # Filter out patterns that already exist in enabled preset categories
        preset_overlaps = []
        final_patterns = []
        for pattern in unique_patterns:
            if pattern in preset_patterns:
                preset_overlaps.append(pattern)
            else:
                final_patterns.append(pattern)
        
        # Update blocklist with validated, deduplicated patterns
        self.blocklist.custom_patterns = final_patterns
        
        # Update AI fallback setting
        self.use_ai_fallback = self.ai_fallback_var.get()
        
        # Save to file
        self.blocklist_manager.save(self.blocklist)
        
        # Show message if any duplicates were handled
        messages = []
        if duplicates_removed:
            messages.append(f"Removed {len(duplicates_removed)} duplicate(s)")
        if preset_overlaps:
            messages.append(f"Removed {len(preset_overlaps)} pattern(s) already in preset categories")
        
        if messages:
            messagebox.showinfo(
                "Blocklist Saved",
                "\n".join(messages) + "\n\nSettings saved successfully."
            )
        
        # Close dialog
        settings_window.destroy()
        
        logger.info(f"Blocklist settings saved (AI fallback: {self.use_ai_fallback}, "
                   f"duplicates removed: {len(duplicates_removed)}, "
                   f"preset overlaps: {len(preset_overlaps)})")
    
    def _draw_status_dot(self, color: str, emoji: str = None):
        """
        Draw the status indicator dot (circle) or emoji.
        
        Args:
            color: Hex color for the dot (used if no emoji)
            emoji: Optional emoji to show instead of the dot
        """
        self.status_dot.delete("all")
        
        if emoji:
            # Show emoji instead of dot
            self.status_dot.create_text(
                7, 7,  # Center of the 14x14 canvas
                text=emoji,
                font=("SF Pro Display", 10),
                anchor="center"
            )
        else:
            # Draw a perfect circle
            self.status_dot.create_oval(1, 1, 13, 13, fill=color, outline="")
    
    def _check_privacy(self):
        """Check if privacy notice has been accepted, show if not."""
        if not PRIVACY_FILE.exists():
            self._show_privacy_notice()
    
    def _show_privacy_notice(self):
        """Display the privacy notice popup."""
        privacy_text = """Gavin AI uses OpenAI's Vision API to monitor your focus sessions.

How it works:
• Camera frames are sent to OpenAI for analysis
• AI detects your presence and gadget distractions
• No video is recorded or stored locally

Privacy:
• OpenAI may retain data for up to 30 days for abuse monitoring
• No data is stored long-term
• All detection happens in real-time

By clicking 'I Understand', you acknowledge this data processing."""
        
        result = messagebox.askokcancel(
            "Privacy Notice",
            privacy_text,
            icon="info"
        )
        
        if result:
            # Save acceptance
            PRIVACY_FILE.parent.mkdir(parents=True, exist_ok=True)
            PRIVACY_FILE.write_text(datetime.now().isoformat())
            logger.info("Privacy notice accepted")
        else:
            # User declined - close app
            self.root.destroy()
    
    def _check_usage_limit(self):
        """Check if usage time is exhausted and show lockout if needed."""
        if self.usage_limiter.is_time_exhausted():
            self.is_locked = True
            self._show_lockout_overlay()
            logger.info("App locked - usage time exhausted")
        else:
            self.is_locked = False
            self._update_time_badge()
    
    def _update_usage_display(self):
        """Update the time badge display periodically."""
        if not self.is_locked:
            self._update_time_badge()
        
        # Calculate actual remaining time (same as badge display)
        base_remaining = self.usage_limiter.get_remaining_seconds()
        if self.is_running and self.session_started and self.session_start_time:
            session_elapsed = int((datetime.now() - self.session_start_time).total_seconds())
            remaining = max(0, base_remaining - session_elapsed)
        else:
            remaining = base_remaining
        
        # Determine update interval based on actual remaining time
        if self.is_running:
            if remaining <= 10:
                # Update every second when time is very low
                update_interval = 1000
            elif remaining <= 60:
                # Update every 2 seconds when under a minute
                update_interval = 2000
            else:
                # Normal: every 5 seconds during session
                update_interval = 5000
        else:
            # When not running, update less frequently
            update_interval = 30000
        
        self.root.after(update_interval, self._update_usage_display)
    
    def _update_time_badge(self):
        """Update the time remaining badge text and color."""
        # Get base remaining time from usage limiter
        base_remaining = self.usage_limiter.get_remaining_seconds()
        
        # If session is running, subtract current session's elapsed active time
        if self.is_running and self.session_started and self.session_start_time:
            # When paused, use frozen value - don't recalculate
            if self.is_paused:
                active_elapsed = self.frozen_active_seconds
            else:
                # Calculate active time (total elapsed minus all paused time)
                elapsed = (datetime.now() - self.session_start_time).total_seconds()
                active_elapsed = int(elapsed - self.total_paused_seconds)
            
            remaining = max(0, base_remaining - active_elapsed)
        else:
            remaining = base_remaining
        
        time_text = self.usage_limiter.format_time(int(remaining))
        
        # Determine badge color based on remaining time
        if remaining <= 0:
            badge_color = COLORS["time_badge_expired"]
            time_text = "Time expired"
        elif remaining <= 600:  # 10 minutes or less
            badge_color = COLORS["time_badge_expired"]
            time_text = f"{time_text} left"
        elif remaining <= 1800:  # 30 minutes or less
            badge_color = COLORS["time_badge_low"]
            time_text = f"{time_text} left"
        else:
            badge_color = COLORS["time_badge"]
            time_text = f"{time_text} left"
        
        self.time_badge.configure(text=time_text, bg=badge_color)
    
    def _show_usage_details(self, event=None):
        """Show a popup with detailed usage information."""
        summary = self.usage_limiter.get_status_summary()
        
        # Add extension info
        if self.usage_limiter.is_time_exhausted():
            summary += "\n\nClick 'Request More Time' to unlock additional usage."
        
        messagebox.showinfo("Usage Details", summary)
    
    def _show_lockout_overlay(self):
        """Show the lockout overlay when time is exhausted."""
        if self.lockout_frame is not None:
            return  # Already showing
        
        # Create overlay frame that covers the main content
        self.lockout_frame = tk.Frame(
            self.main_frame,
            bg=COLORS["bg_dark"]
        )
        self.lockout_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        # Center content
        content_frame = tk.Frame(self.lockout_frame, bg=COLORS["bg_dark"])
        content_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Expired icon/text
        expired_label = tk.Label(
            content_frame,
            text="⏱️",
            font=tkfont.Font(size=48),
            fg=COLORS["text_primary"],
            bg=COLORS["bg_dark"]
        )
        expired_label.pack(pady=(0, 10))
        
        title_label = tk.Label(
            content_frame,
            text="Time Exhausted",
            font=self.font_title,
            fg=COLORS["time_badge_expired"],
            bg=COLORS["bg_dark"]
        )
        title_label.pack(pady=(0, 10))
        
        message_label = tk.Label(
            content_frame,
            text="Your trial time has run out.\nRequest more time to continue using Gavin AI.",
            font=self.font_status,
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_dark"],
            justify="center"
        )
        message_label.pack(pady=(0, 20))
        
        # Request More Time button
        request_btn = RoundedButton(
            content_frame,
            text="Request More Time",
            command=self._show_password_dialog,
            bg_color=COLORS["accent_primary"],
            hover_color="#0EA5E9",
            fg_color=COLORS["text_white"],
            font=self.font_button,
            corner_radius=10,
            width=200,
            height=52
        )
        request_btn.pack()
        
        # Update badge to show expired state
        self._update_time_badge()
        
        # Disable start button
        self.start_stop_btn.configure_button(state=tk.DISABLED)
    
    def _hide_lockout_overlay(self):
        """Hide the lockout overlay after successful unlock."""
        if self.lockout_frame is not None:
            self.lockout_frame.destroy()
            self.lockout_frame = None
        
        self.is_locked = False
        self._update_time_badge()
        
        # Re-enable start button
        self.start_stop_btn.configure_button(state=tk.NORMAL)
        
        logger.info("App unlocked - time extension granted")
    
    def _show_password_dialog(self):
        """Show dialog to enter unlock password."""
        # Create dialog window
        dialog = tk.Toplevel(self.root)
        dialog.title("Unlock More Time")
        dialog.configure(bg=COLORS["bg_dark"])
        dialog.resizable(False, False)
        
        # Size and position - center on screen (like main Gavin UI)
        dialog_width = 350
        dialog_height = 200
        dialog.update_idletasks()
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        
        # Make modal
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Content
        content = tk.Frame(dialog, bg=COLORS["bg_dark"])
        content.pack(fill=tk.BOTH, expand=True, padx=25, pady=20)
        
        title = tk.Label(
            content,
            text="Enter Password",
            font=self.font_status,
            fg=COLORS["text_primary"],
            bg=COLORS["bg_dark"]
        )
        title.pack(pady=(0, 5))
        
        extension_time = self.usage_limiter.format_time(config.MVP_EXTENSION_SECONDS)
        subtitle = tk.Label(
            content,
            text=f"Enter the unlock password to add {extension_time} more",
            font=self.font_small,
            fg=COLORS["text_secondary"],
            bg=COLORS["bg_dark"]
        )
        subtitle.pack(pady=(0, 15))
        
        # Password entry
        password_var = tk.StringVar()
        password_entry = tk.Entry(
            content,
            textvariable=password_var,
            show="•",
            font=self.font_status,
            width=25
        )
        password_entry.pack(pady=(0, 10))
        password_entry.focus_set()
        
        # Error label (hidden initially)
        error_label = tk.Label(
            content,
            text="",
            font=self.font_small,
            fg=COLORS["time_badge_expired"],
            bg=COLORS["bg_dark"]
        )
        error_label.pack(pady=(0, 10))
        
        def try_unlock():
            """Attempt to unlock with entered password."""
            password = password_var.get()
            
            if not password:
                error_label.configure(text="Please enter a password")
                return
            
            if self.usage_limiter.validate_password(password):
                # Grant extension
                extension_seconds = self.usage_limiter.grant_extension()
                extension_time = self.usage_limiter.format_time(extension_seconds)
                dialog.destroy()
                self._hide_lockout_overlay()
                messagebox.showinfo(
                    "Time Added",
                    f"{extension_time} has been added to your account.\n\n"
                    f"New balance: {self.usage_limiter.format_time(self.usage_limiter.get_remaining_seconds())}"
                )
            else:
                error_label.configure(text="Incorrect password")
                password_var.set("")
                password_entry.focus_set()
        
        # Bind Enter key
        password_entry.bind("<Return>", lambda e: try_unlock())
        
        # Buttons frame
        btn_frame = tk.Frame(content, bg=COLORS["bg_dark"])
        btn_frame.pack(fill=tk.X)
        
        cancel_btn = tk.Button(
            btn_frame,
            text="Cancel",
            command=dialog.destroy,
            font=self.font_small,
            width=10
        )
        cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        unlock_btn = tk.Button(
            btn_frame,
            text="Unlock",
            command=try_unlock,
            font=self.font_small,
            width=10
        )
        unlock_btn.pack(side=tk.RIGHT)
    
    def _on_enter_key(self, event=None):
        """
        Handle Enter key press to start/stop session.
        
        Args:
            event: Key event (unused but required for binding)
        """
        # Don't toggle if locked or if focus is on an Entry widget (e.g., password dialog)
        if self.is_locked:
            return
        
        # Check if focus is on an Entry widget (don't intercept typing)
        focused_widget = self.root.focus_get()
        if isinstance(focused_widget, tk.Entry):
            return
        
        self._toggle_session()
    
    def _toggle_session(self):
        """Toggle between starting and stopping a session."""
        if not self.is_running:
            self._start_session()
        else:
            self._stop_session()
    
    def _toggle_pause(self):
        """Toggle between pausing and resuming a session."""
        if not self.is_paused:
            self._pause_session()
        else:
            self._resume_session()
    
    def _pause_session(self):
        """
        Pause the current session INSTANTLY.
        
        Logs a pause event, freezes the timer at the exact moment, and stops API calls.
        Uses int() truncation to floor the value (32.9s becomes 32s, not 33s).
        Forces immediate UI update to prevent any visual lag.
        """
        if not self.is_running or self.is_paused:
            return
        
        # CRITICAL: Set is_paused FIRST to prevent any timer updates from racing
        self.is_paused = True
        
        # Capture exact pause moment
        self.pause_start_time = datetime.now()
        
        # Calculate and freeze the active seconds at this exact moment
        # int() truncates (floors) - so 32.9s becomes 32s, not 33s
        if self.session_start_time:
            elapsed = (self.pause_start_time - self.session_start_time).total_seconds()
            self.frozen_active_seconds = int(elapsed - self.total_paused_seconds)
        
        # Log the pause event in the session
        if self.session and self.session_started:
            self.session.log_event(config.EVENT_PAUSED)
        
        # Reset unfocused alert tracking (shouldn't alert while paused)
        self.unfocused_start_time = None
        self.alerts_played = 0
        
        # Update UI instantly with frozen value
        self._update_status("paused", "Paused")
        self.pause_btn.configure_button(
            text="Resume Session",
            bg_color=COLORS["button_resume"],
            hover_color=COLORS["button_resume_hover"]
        )
        
        # Display frozen timer value immediately
        hours = self.frozen_active_seconds // 3600
        minutes = (self.frozen_active_seconds % 3600) // 60
        secs = self.frozen_active_seconds % 60
        self.timer_label.configure(text=f"{hours:02d}:{minutes:02d}:{secs:02d}")
        
        # FORCE IMMEDIATE UI REFRESH - ensures display updates before any other events
        self.root.update_idletasks()
        
        # Update usage badge
        self._update_time_badge()
        
        logger.info("Session paused")
        print(f"⏸ Session paused ({self.pause_start_time.strftime('%I:%M %p')})")
    
    def _resume_session(self):
        """
        Resume the paused session.
        
        Calculates pause duration with full precision, logs return to present state.
        """
        if not self.is_running or not self.is_paused:
            return
        
        resume_time = datetime.now()
        
        # Calculate pause duration with full precision (no rounding)
        if self.pause_start_time:
            pause_duration = (resume_time - self.pause_start_time).total_seconds()
            self.total_paused_seconds += pause_duration
        
        self.is_paused = False
        self.pause_start_time = None
        self.frozen_active_seconds = 0  # Clear frozen value
        
        # Log return to present state in the session
        if self.session and self.session_started:
            self.session.log_event(config.EVENT_PRESENT)
        
        # Update UI
        self._update_status("focused", "Focused")
        self.pause_btn.configure_button(
            text="Pause Session",
            bg_color=COLORS["button_pause"],
            hover_color=COLORS["button_pause_hover"]
        )
        
        logger.info("Session resumed")
        print(f"▶ Session resumed ({resume_time.strftime('%I:%M %p')})")
    
    def _start_session(self):
        """Start a new focus session."""
        # Check if locked due to usage limit
        if self.is_locked:
            messagebox.showwarning(
                "Time Exhausted",
                "Your trial time has run out.\n\n"
                "Click 'Request More Time' to unlock additional usage."
            )
            return
        
        # Check if there's enough time remaining
        if self.usage_limiter.is_time_exhausted():
            self.is_locked = True
            self._show_lockout_overlay()
            return
        
        # Verify API key exists (only required for camera modes)
        needs_camera = self.monitoring_mode in (config.MODE_CAMERA_ONLY, config.MODE_BOTH)
        if needs_camera and not config.OPENAI_API_KEY:
            messagebox.showerror(
                "API Key Required",
                "OpenAI API key not found!\n\n"
                "Please set OPENAI_API_KEY in your .env file.\n"
                "Get your key from: https://platform.openai.com/api-keys"
            )
            return
        
        # Initialize session (but don't start yet - wait for first detection)
        self.session = Session()
        self.session_started = False  # Will start on first detection
        self.session_start_time = None  # Timer starts after bootup
        self.is_running = True
        self.should_stop.clear()
        
        # Reset pause state for new session
        self.is_paused = False
        self.pause_start_time = None
        self.total_paused_seconds = 0.0
        self.frozen_active_seconds = 0
        
        # Reset unfocused alert tracking for new session
        self.unfocused_start_time = None
        self.alerts_played = 0
        
        # Hide mode selector during session
        self.mode_frame.grid_remove()
        
        # Update UI - show both buttons (pause on top, stop below)
        self._update_status("focused", "Booting Up...", emoji="⚡️")
        
        # Repack buttons in correct order: pause on top, stop below with gap
        self.start_stop_btn.pack_forget()  # Remove stop button temporarily
        self.pause_btn.pack(pady=(0, 15))  # Pause button first with gap below
        self.pause_btn.configure_button(
            text="Pause Session",
            bg_color=COLORS["button_pause"],
            hover_color=COLORS["button_pause_hover"]
        )
        self.start_stop_btn.pack()  # Stop button below
        self.start_stop_btn.configure_button(
            text="Stop Session",
            bg_color=COLORS["button_stop"],
            hover_color=COLORS["button_stop_hover"]
        )
        
        # Start appropriate detection thread(s) based on monitoring mode
        if self.monitoring_mode == config.MODE_CAMERA_ONLY:
            # Camera only mode (existing behavior)
            self.detection_thread = threading.Thread(
                target=self._detection_loop,
                daemon=True
            )
            self.detection_thread.start()
        elif self.monitoring_mode == config.MODE_SCREEN_ONLY:
            # Screen only mode
            self.detection_thread = threading.Thread(
                target=self._screen_detection_loop,
                daemon=True
            )
            self.detection_thread.start()
        else:
            # Both camera and screen monitoring
            self.detection_thread = threading.Thread(
                target=self._detection_loop,
                daemon=True
            )
            self.detection_thread.start()
            
            self.screen_detection_thread = threading.Thread(
                target=self._screen_detection_loop,
                daemon=True
            )
            self.screen_detection_thread.start()
        
        logger.info(f"Session started via GUI (mode: {self.monitoring_mode})")
    
    def _stop_session(self):
        """Stop the current session INSTANTLY and auto-generate report."""
        if not self.is_running:
            return
        
        # Capture stop time IMMEDIATELY when user clicks stop
        stop_time = datetime.now()
        
        # If paused, finalize the pause duration before stopping (full precision)
        if self.is_paused and self.pause_start_time:
            pause_duration = (stop_time - self.pause_start_time).total_seconds()
            self.total_paused_seconds += pause_duration
            self.is_paused = False
            self.pause_start_time = None
        
        # Signal thread to stop
        self.should_stop.set()
        self.is_running = False
        
        # Wait for detection thread(s) to finish
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join(timeout=2.0)
        if self.screen_detection_thread and self.screen_detection_thread.is_alive():
            self.screen_detection_thread.join(timeout=2.0)
        
        # Show mode selector again
        self.mode_frame.grid()
        
        # End session (only if it was actually started after first detection)
        if self.session and self.session_started and self.session_start_time:
            # Calculate and record session duration (excluding paused time)
            # Use full precision until final int conversion for usage tracking
            total_elapsed = (stop_time - self.session_start_time).total_seconds()
            active_duration = int(total_elapsed - self.total_paused_seconds)
            self.usage_limiter.record_usage(active_duration)
            
            self.session.end(stop_time)  # Use the captured stop time
            self.usage_limiter.end_session()
        
        # Hide pause button when session stops
        self.pause_btn.pack_forget()
        
        # Update UI to show generating status
        self._update_status("idle", "Generating Reports...")
        self.start_stop_btn.configure_button(
            text="Generating...",
            state=tk.DISABLED
        )
        self.root.update()
        
        # Update time badge after session ends
        self._update_time_badge()
        
        logger.info("Session stopped via GUI")
        
        # Auto-generate report
        self._generate_report()
    
    def _detection_loop(self):
        """
        Main detection loop running in a separate thread.
        
        Captures frames from camera and analyzes them using OpenAI Vision API.
        Also handles unfocused alerts at configured thresholds and usage tracking.
        """
        try:
            detector = VisionDetector()
            
            with CameraCapture() as camera:
                if not camera.is_opened:
                    self.root.after(0, lambda: self._show_camera_error())
                    return
                
                last_detection_time = time.time()
                
                for frame in camera.frame_iterator():
                    if self.should_stop.is_set():
                        break
                    
                    # Skip all detection when paused (no API calls)
                    if self.is_paused:
                        time.sleep(0.1)  # Sleep longer when paused to reduce CPU
                        continue
                    
                    # Throttle detection to configured FPS
                    current_time = time.time()
                    time_since_detection = current_time - last_detection_time
                    
                    # Note: Time exhaustion is checked in _update_timer to stay in sync with display
                    
                    if time_since_detection >= (1.0 / config.DETECTION_FPS):
                        # Perform detection using OpenAI Vision
                        detection_state = detector.get_detection_state(frame)
                        
                        # Re-check stop signal after detection (API call takes 2-3 seconds)
                        # User may have clicked Stop during this time
                        if self.should_stop.is_set():
                            break
                        
                        # Also check if paused during detection (user may have paused during API call)
                        if self.is_paused:
                            continue
                        
                        # Start session on first successful detection (eliminates bootup time)
                        if not self.session_started:
                            self.session.start()
                            self.session_start_time = datetime.now()
                            self.session_started = True
                            logger.info("First detection complete - session timer started")
                        
                        # Determine event type
                        event_type = get_event_type(detection_state)
                        
                        # Check if user is unfocused (away or on gadget)
                        is_unfocused = event_type in (config.EVENT_AWAY, config.EVENT_GADGET_SUSPECTED)
                        
                        if is_unfocused:
                            # Start tracking if not already
                            if self.unfocused_start_time is None:
                                self.unfocused_start_time = current_time
                                self.alerts_played = 0
                                logger.debug("Started tracking unfocused time")
                            
                            # Check if we should play an alert
                            unfocused_duration = current_time - self.unfocused_start_time
                            alert_times = config.UNFOCUSED_ALERT_TIMES
                            
                            # Play alert if duration exceeds next threshold (and we haven't played all 3)
                            if (self.alerts_played < len(alert_times) and 
                                unfocused_duration >= alert_times[self.alerts_played]):
                                self._play_unfocused_alert()
                                self.alerts_played += 1
                        else:
                            # User is focused - reset tracking
                            if self.unfocused_start_time is not None:
                                logger.debug("User refocused - resetting alert tracking")
                                # Dismiss any active notification popup
                                self.root.after(0, self._dismiss_alert_popup)
                            self.unfocused_start_time = None
                            self.alerts_played = 0
                        
                        # Log event
                        if self.session:
                            self.session.log_event(event_type)
                        
                        # Update UI status (thread-safe)
                        self._update_detection_status(event_type)
                        
                        last_detection_time = current_time
                    
                    # Small sleep to prevent CPU overload
                    time.sleep(0.05)
                    
        except Exception as e:
            logger.error(f"Detection loop error: {e}")
            self.root.after(0, lambda: self._show_detection_error(str(e)))
    
    def _screen_detection_loop(self):
        """
        Screen monitoring detection loop running in a separate thread.
        
        Checks active window and browser URL against the blocklist.
        Does NOT use AI API calls - purely local pattern matching.
        """
        try:
            window_detector = WindowDetector()
            
            # Check permissions on first run
            if not window_detector.check_permission():
                instructions = window_detector.get_permission_instructions()
                self.root.after(0, lambda: self._show_screen_permission_error(instructions))
                return
            
            last_screen_check = time.time()
            
            # For screen-only mode, we need to start the session on first check
            if self.monitoring_mode == config.MODE_SCREEN_ONLY:
                # Start session immediately for screen-only mode
                if not self.session_started:
                    self.session.start()
                    self.session_start_time = datetime.now()
                    self.session_started = True
                    logger.info("Screen-only mode - session timer started")
                    # Update UI to show focused status
                    self.root.after(0, lambda: self._update_status("focused", "Focused"))
            
            while not self.should_stop.is_set():
                # Skip when paused
                if self.is_paused:
                    time.sleep(0.1)
                    continue
                
                current_time = time.time()
                time_since_check = current_time - last_screen_check
                
                if time_since_check >= config.SCREEN_CHECK_INTERVAL:
                    # Get current screen state (with optional AI fallback)
                    if self.use_ai_fallback:
                        screen_state = get_screen_state_with_ai_fallback(
                            self.blocklist,
                            use_ai_fallback=True
                        )
                    else:
                        screen_state = get_screen_state(self.blocklist)
                    
                    if self.should_stop.is_set():
                        break
                    
                    if self.is_paused:
                        continue
                    
                    # Check for distraction
                    if screen_state.get("is_distracted", False):
                        distraction_source = screen_state.get("distraction_source", "Unknown")
                        
                        # Log event
                        if self.session and self.session_started:
                            self.session.log_event(config.EVENT_SCREEN_DISTRACTION)
                        
                        # Update UI (thread-safe)
                        self.root.after(0, lambda s=distraction_source: self._update_status(
                            "screen", 
                            f"Screen: {s[:20]}..." if len(s) > 20 else f"Screen: {s}"
                        ))
                        
                        # Track for alerts (same as camera distraction)
                        if self.unfocused_start_time is None:
                            self.unfocused_start_time = current_time
                            self.alerts_played = 0
                            logger.debug("Started tracking screen distraction time")
                        
                        # Check for escalating alerts
                        unfocused_duration = current_time - self.unfocused_start_time
                        alert_times = config.UNFOCUSED_ALERT_TIMES
                        
                        if (self.alerts_played < len(alert_times) and
                            unfocused_duration >= alert_times[self.alerts_played]):
                            self._play_unfocused_alert()
                            self.alerts_played += 1
                    else:
                        # Not distracted - only update if screen-only mode or if camera didn't detect distraction
                        if self.monitoring_mode == config.MODE_SCREEN_ONLY:
                            if self.session and self.session_started:
                                self.session.log_event(config.EVENT_PRESENT)
                            self.root.after(0, lambda: self._update_status("focused", "Focused"))
                            
                            # Reset alert tracking
                            if self.unfocused_start_time is not None:
                                logger.debug("Screen refocused - resetting alert tracking")
                                self.root.after(0, self._dismiss_alert_popup)
                            self.unfocused_start_time = None
                            self.alerts_played = 0
                    
                    last_screen_check = current_time
                
                # Small sleep to prevent CPU overload
                time.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Screen detection loop error: {e}")
            self.root.after(0, lambda: self._show_detection_error(f"Screen monitoring: {str(e)}"))
    
    def _show_screen_permission_error(self, instructions: str):
        """
        Show an error message when screen monitoring permissions are missing.
        
        Args:
            instructions: Platform-specific permission instructions
        """
        messagebox.showerror(
            "Screen Monitoring Permission Required",
            f"Screen monitoring cannot access window information.\n\n{instructions}"
        )
        # Stop the session since screen monitoring failed
        if self.is_running and self.monitoring_mode == config.MODE_SCREEN_ONLY:
            self._stop_session()
    
    def _handle_time_exhausted(self):
        """
        Handle time exhaustion during a running session.
        
        Stops the session, generates PDF report, then shows lockout overlay.
        """
        # Capture stop time immediately
        stop_time = datetime.now()
        
        # Stop the current session
        if self.is_running:
            # If paused, finalize the pause duration before stopping (full precision)
            if self.is_paused and self.pause_start_time:
                pause_duration = (stop_time - self.pause_start_time).total_seconds()
                self.total_paused_seconds += pause_duration
                self.is_paused = False
                self.pause_start_time = None
            
            self.should_stop.set()
            self.is_running = False
            
            # End session with captured stop time
            if self.session and self.session_started and self.session_start_time:
                # Calculate and record session duration (excluding paused time)
                # Use full precision until final int conversion for usage tracking
                total_elapsed = (stop_time - self.session_start_time).total_seconds()
                active_duration = int(total_elapsed - self.total_paused_seconds)
                self.usage_limiter.record_usage(active_duration)
                
                self.session.end(stop_time)
                self.usage_limiter.end_session()
            
            # Hide pause button when session stops
            self.pause_btn.pack_forget()
            
            # Update UI to show generating status
            self._update_status("idle", "Generating Reports...")
            self.start_stop_btn.configure_button(
                text="Generating...",
                state=tk.DISABLED
            )
            self.root.update()
            
            logger.info("Session stopped due to time exhaustion - generating report")
            
            # Generate PDF report before lockout
            self._generate_report_for_lockout()
        
        # Show lockout
        self.is_locked = True
        self._show_lockout_overlay()
        
        # Notify user (after report generation so they know report was saved)
        messagebox.showwarning(
            "Time Exhausted",
            "Your trial time has run out.\n\n"
            "Your session report has been saved to Downloads.\n\n"
            "Click 'Request More Time' to unlock additional usage."
        )
    
    def _generate_report_for_lockout(self):
        """
        Generate PDF report when session ends due to time exhaustion.
        
        Similar to _generate_report but without prompting to open the file.
        """
        if not self.session or not self.session_started:
            self._reset_button_state()
            return
        
        try:
            # Compute statistics
            stats = compute_statistics(
                self.session.events,
                self.session.get_duration()
            )
            
            # Generate PDF (combined summary + logs)
            report_path = generate_report(
                stats,
                self.session.session_id,
                self.session.start_time,
                self.session.end_time
            )
            
            # Reset UI
            self._reset_button_state()
            
            logger.info(f"Report generated (time exhausted): {report_path}")
            
        except Exception as e:
            logger.error(f"Report generation failed during lockout: {e}")
            self._reset_button_state()
    
    def _update_detection_status(self, event_type: str):
        """
        Update the status display based on detection result.
        
        Args:
            event_type: Type of event detected
        """
        status_map = {
            config.EVENT_PRESENT: ("focused", "Focused"),
            config.EVENT_AWAY: ("away", "Away from Desk"),
            config.EVENT_GADGET_SUSPECTED: ("gadget", "On another gadget"),
            config.EVENT_SCREEN_DISTRACTION: ("screen", "Screen distraction"),
        }
        
        status, text = status_map.get(event_type, ("idle", "Unknown"))
        
        # Schedule UI update on main thread
        self.root.after(0, lambda: self._update_status(status, text))
    
    def _update_status(self, status: str, text: str, emoji: str = None):
        """
        Update the status indicator and label.
        
        Args:
            status: Status type (idle, focused, away, gadget, screen, paused)
            text: Display text
            emoji: Optional emoji to show instead of the colored dot
        """
        with self.ui_lock:
            self.current_status = status
            color = self._get_current_status_color()
            self._draw_status_dot(color, emoji=emoji)
            self.status_label.configure(text=text)
    
    def _update_timer(self):
        """
        Update the timer display frequently for instant pause feel.
        
        Timer updates every 100ms for smooth display and instant pause response.
        Usage badge and other expensive operations update every second.
        """
        if self.is_running and self.session_start_time:
            # When paused, use frozen value - don't recalculate
            if self.is_paused:
                active_seconds = self.frozen_active_seconds
            else:
                # Calculate active time (total elapsed minus all paused time)
                elapsed = (datetime.now() - self.session_start_time).total_seconds()
                active_seconds = int(elapsed - self.total_paused_seconds)
            
            hours = active_seconds // 3600
            minutes = (active_seconds % 3600) // 60
            secs = active_seconds % 60
            
            time_str = f"{hours:02d}:{minutes:02d}:{secs:02d}"
            self.timer_label.configure(text=time_str)
            
            # Only check usage limits and update badge every second (not every 100ms)
            # This reduces overhead while keeping timer display smooth
            if not self.is_paused and not self.is_locked:
                # Track when we last did expensive operations
                current_second = active_seconds
                if not hasattr(self, '_last_usage_check_second'):
                    self._last_usage_check_second = -1
                
                if current_second != self._last_usage_check_second:
                    self._last_usage_check_second = current_second
                    self._update_time_badge()
                    
                    # Check if time exhausted
                    base_remaining = self.usage_limiter.get_remaining_seconds()
                    actual_remaining = base_remaining - active_seconds
                    if actual_remaining <= 0:
                        logger.warning("Usage time exhausted during session")
                        self._handle_time_exhausted()
                        return  # Don't schedule next update, session is ending
        
        # Schedule next update at 100ms for smooth display and instant pause response
        self.root.after(100, self._update_timer)
    
    def _play_unfocused_alert(self):
        """
        Play the custom Gavin alert sound and show notification popup.
        
        Uses the custom MP3 file in data/gavin alert sound.mp3
        Cross-platform playback:
        - macOS: afplay (native MP3 support)
        - Windows: start command with default media player
        - Linux: mpg123 or ffplay
        
        Also displays a supportive notification popup that auto-dismisses.
        """
        # Get the alert data for this level (badge_text, message)
        alert_index = self.alerts_played  # 0, 1, or 2
        badge_text, message = config.UNFOCUSED_ALERT_MESSAGES[alert_index]
        
        def play_sound():
            # Path to custom alert sound
            sound_file = Path(__file__).parent.parent / "data" / "gavin_alert_sound.mp3"
            
            if not sound_file.exists():
                logger.warning(f"Alert sound file not found: {sound_file}")
                return
            
            try:
                if sys.platform == "darwin":
                    # macOS - afplay supports MP3
                    subprocess.Popen(
                        ["afplay", str(sound_file)],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                elif sys.platform == "win32":
                    # Windows - use powershell to play media file
                    subprocess.Popen(
                        ["powershell", "-c", f'(New-Object Media.SoundPlayer "{sound_file}").PlaySync()'],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                else:
                    # Linux - try mpg123 first, fallback to ffplay
                    try:
                        subprocess.Popen(
                            ["mpg123", "-q", str(sound_file)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                    except FileNotFoundError:
                        subprocess.Popen(
                            ["ffplay", "-nodisp", "-autoexit", str(sound_file)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
            except Exception as e:
                logger.debug(f"Sound playback error: {e}")
        
        # Play sound first (synchronously start the process)
        play_sound()
        
        # Show notification popup on main thread (1 second delay to sync with sound)
        self.root.after(1500, lambda: self._show_alert_popup(badge_text, message))
        
        logger.info(f"Unfocused alert #{self.alerts_played + 1} played")
    
    def _show_alert_popup(self, badge_text: str, message: str):
        """
        Display the notification popup with badge and message.
        
        Args:
            badge_text: The badge/pill text (e.g., "Focus paused")
            message: The main supportive message to show
        """
        try:
            NotificationPopup(
                self.root,
                badge_text=badge_text,
                message=message,
                duration_seconds=config.ALERT_POPUP_DURATION
            )
        except Exception as e:
            logger.error(f"Failed to show notification popup: {e}")
    
    def _dismiss_alert_popup(self):
        """Dismiss any active notification popup when user refocuses."""
        if NotificationPopup._active_popup is not None:
            NotificationPopup._active_popup.dismiss()
            logger.debug("Dismissed alert popup - user refocused")
    
    def _generate_report(self):
        """Generate PDF report for the completed session."""
        if not self.session or not self.session_started:
            # No session or session never got first detection
            self._reset_button_state()
            self._update_status("idle", "Ready to Start")
            if not self.session_started:
                messagebox.showinfo(
                    "No Session Data",
                    "Session was stopped before any detection occurred.\n"
                    "No report generated."
                )
            return
        
        try:
            # Compute statistics
            stats = compute_statistics(
                self.session.events,
                self.session.get_duration()
            )
            
            # Generate PDF (combined summary + logs)
            report_path = generate_report(
                stats,
                self.session.session_id,
                self.session.start_time,
                self.session.end_time
            )
            
            # Reset UI
            self._reset_button_state()
            self._update_status("idle", "Report Generated!")
            
            # Show success and offer to open report
            result = messagebox.askyesno(
                "Report Generated",
                f"Report saved to:\n\n"
                f"{report_path.name}\n\n"
                f"Location: {report_path.parent}\n\n"
                "Would you like to open the report?"
            )
            
            if result:
                self._open_file(report_path)
            
            # Reset status after showing dialog
            self._update_status("idle", "Ready to Start")
            
            logger.info(f"Report generated: {report_path}")
            
        except Exception as e:
            logger.error(f"Report generation failed: {e}")
            self._reset_button_state()
            self._update_status("idle", "Ready to Start")
            messagebox.showerror(
                "Report Error",
                f"Failed to generate report:\n{str(e)}"
            )
    
    def _reset_button_state(self):
        """Reset the button to its initial state."""
        self.start_stop_btn.configure_button(
            text="Start Session",
            bg_color=COLORS["button_start"],
            hover_color=COLORS["button_start_hover"],
            state=tk.NORMAL
        )
        self.timer_label.configure(text="00:00:00")
    
    def _open_file(self, filepath: Path):
        """
        Open a file with the system's default application.
        
        Args:
            filepath: Path to the file to open
        """
        try:
            if sys.platform == "darwin":  # macOS
                subprocess.run(["open", str(filepath)], check=True)
            elif sys.platform == "win32":  # Windows
                os.startfile(str(filepath))
            else:  # Linux
                subprocess.run(["xdg-open", str(filepath)], check=True)
        except Exception as e:
            logger.error(f"Failed to open file: {e}")
    
    def _show_camera_error(self):
        """Show camera access error dialog."""
        messagebox.showerror(
            "Camera Error",
            "Failed to access webcam.\n\n"
            "Please check:\n"
            "• Camera is connected\n"
            "• Camera permissions are granted\n"
            "• No other app is using the camera"
        )
        self._reset_button_state()
        self._update_status("idle", "Ready to Start")
    
    def _show_detection_error(self, error: str):
        """
        Show detection error dialog.
        
        Args:
            error: Error message
        """
        messagebox.showerror(
            "Detection Error",
            f"An error occurred during detection:\n\n{error}"
        )
        self._reset_button_state()
        self._update_status("idle", "Ready to Start")
    
    def _on_close(self):
        """Handle window close event."""
        if self.is_running:
            result = messagebox.askyesno(
                "Session Active",
                "A session is currently running.\n\n"
                "Would you like to stop the session and exit?\n"
                "(Report will be generated)"
            )
            if not result:
                return
            
            # Capture stop time immediately
            stop_time = datetime.now()
            
            # If paused, finalize the pause duration before stopping
            if self.is_paused and self.pause_start_time:
                pause_duration = (stop_time - self.pause_start_time).total_seconds()
                self.total_paused_seconds += pause_duration
                self.is_paused = False
                self.pause_start_time = None
            
            # Stop session
            self.should_stop.set()
            self.is_running = False
            if self.detection_thread and self.detection_thread.is_alive():
                self.detection_thread.join(timeout=2.0)
            
            # End session and record usage with correct active duration
            if self.session and self.session_started and self.session_start_time:
                total_elapsed = (stop_time - self.session_start_time).total_seconds()
                active_duration = int(total_elapsed - self.total_paused_seconds)
                self.usage_limiter.record_usage(active_duration)
                self.session.end(stop_time)
                self.usage_limiter.end_session()
            elif self.session:
                self.session.end(stop_time)
        
        self.root.destroy()
    
    def run(self):
        """Start the GUI application main loop."""
        logger.info("Starting Gavin AI GUI")
        self.root.mainloop()


def main():
    """Entry point for the GUI application."""
    # Configure logging
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL),
        format=config.LOG_FORMAT
    )
    
    # Suppress noisy third-party logs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    # Check for existing instance (single instance enforcement)
    if not check_single_instance():
        existing_pid = get_existing_pid()
        pid_info = f" (PID: {existing_pid})" if existing_pid else ""
        
        # Show error dialog
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Gavin AI Already Running",
            f"Another instance of Gavin AI is already running{pid_info}.\n\n"
            "Only one instance can run at a time.\n"
            "Please close the other instance first."
        )
        root.destroy()
        sys.exit(1)
    
    # Check for API key early
    if not config.OPENAI_API_KEY:
        logger.warning("OpenAI API key not found - user will be prompted")
    
    # Create and run GUI
    app = GavinGUI()
    app.run()


if __name__ == "__main__":
    main()
