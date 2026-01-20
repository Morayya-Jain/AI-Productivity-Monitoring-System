"""Session management and event logging."""

from datetime import datetime
from typing import Dict, List, Optional, Any
import config


class Session:
    """
    Manages a single focus session with event logging.
    
    Tracks session lifecycle, logs events (present, away, gadget_suspected,
    screen_distraction), and provides JSON serialization for persistence.
    """
    
    def __init__(self, session_id: Optional[str] = None):
        """
        Initialize a new session.
        
        Args:
            session_id: Optional custom session ID. If None, generates timestamp-based ID.
        """
        self.session_id = session_id or self._generate_session_id()
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.events: List[Dict[str, Any]] = []
        self.current_state: Optional[str] = None
        self.state_start_time: Optional[datetime] = None
        
    def _generate_session_id(self) -> str:
        """Generate a human-readable session ID with day and time."""
        now = datetime.now()
        day = now.strftime("%A")  # Full day name: Monday, Tuesday, etc.
        time = now.strftime("%I.%M %p")  # Time format: 2.45PM, 9.30AM
        
        return f"Gavin-AI {day} {time}"
    
    def start(self) -> None:
        """Start the session and log the start time."""
        self.start_time = datetime.now()
        self.current_state = config.EVENT_PRESENT
        self.state_start_time = self.start_time
        print(f"✓ Session started at {self.start_time.strftime('%I:%M %p')}")
    
    def end(self, end_time: Optional[datetime] = None) -> None:
        """
        End the session, finalize the current state, and log the end time.
        
        Args:
            end_time: Optional end timestamp. If None, uses current time.
                      Pass explicit time to ensure accuracy when called after delays.
        """
        self.end_time = end_time or datetime.now()
        
        # Finalize the last state if it exists
        if self.current_state and self.state_start_time:
            self._finalize_current_state(self.end_time)
        
        duration = self.get_duration()
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        
        if hours > 0:
            duration_str = f"{hours}h {minutes}m"
        else:
            duration_str = f"{minutes}m"
            
        print(f"Session ended. Duration: {duration_str}")
    
    def log_event(self, event_type: str, timestamp: Optional[datetime] = None) -> None:
        """
        Log a state change event.
        
        When the state changes (e.g., present -> away), this method:
        1. Finalizes the previous state by calculating its duration
        2. Starts tracking the new state
        
        Args:
            event_type: Type of event (present, away, gadget_suspected, 
                        screen_distraction, paused)
            timestamp: Optional timestamp. If None, uses current time.
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        # If this is a state change, finalize the previous state
        if event_type != self.current_state:
            # Save previous state for console message logic
            previous_state = self.current_state
            
            if self.current_state and self.state_start_time:
                self._finalize_current_state()
            
            # Start new state
            self.current_state = event_type
            self.state_start_time = timestamp
            
            # Print console update for major events
            # Note: Pause/resume messages are handled by the GUI directly
            if event_type == config.EVENT_AWAY:
                print(f"⚠ Moved away from desk ({timestamp.strftime('%I:%M %p')})")
            elif event_type == config.EVENT_PRESENT:
                # Don't print "Back at desk" when resuming from pause
                # The GUI already prints "▶ Session resumed" for that case
                if previous_state != config.EVENT_PAUSED:
                    print(f"✓ Back at desk ({timestamp.strftime('%I:%M %p')})")
            elif event_type == config.EVENT_GADGET_SUSPECTED:
                print(f"📱 On another gadget ({timestamp.strftime('%I:%M %p')})")
            elif event_type == config.EVENT_SCREEN_DISTRACTION:
                print(f"🖥 Screen distraction detected ({timestamp.strftime('%I:%M %p')})")
            elif event_type == config.EVENT_PAUSED:
                # Pause message is handled by GUI, but log for consistency
                pass  # GUI prints "⏸ Session paused"
    
    def _finalize_current_state(self, end_time: Optional[datetime] = None) -> None:
        """
        Finalize the current state by calculating its duration and adding to events.
        
        Args:
            end_time: Optional end timestamp. If None, uses current time.
        """
        if not self.current_state or not self.state_start_time:
            return
        
        actual_end_time = end_time or datetime.now()
        duration = (actual_end_time - self.state_start_time).total_seconds()
        
        event = {
            "type": self.current_state,
            "start": self.state_start_time.isoformat(),
            "end": actual_end_time.isoformat(),
            "duration_seconds": duration
        }
        
        self.events.append(event)
    
    def get_duration(self) -> float:
        """
        Get total session duration in seconds.
        
        Returns:
            Total duration in seconds, or 0 if session hasn't started.
        """
        if not self.start_time:
            return 0.0
        
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

