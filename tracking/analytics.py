"""Analytics for computing session statistics from events."""

from typing import Dict, List, Any
from datetime import datetime
import config


def compute_statistics(events: List[Dict[str, Any]], total_duration: float) -> Dict[str, Any]:
    """
    Compute statistics from a list of session events.
    
    All calculations use floats for full precision.
    Truncation to int happens ONLY at final PDF display time.
    
    To ensure summary matches sum of displayed logs, we sum int(each duration).
    This way: summary = sum of what each log entry displays.
    
    Args:
        events: List of event dictionaries with type, start, end, and duration
        total_duration: Total session duration in seconds (for reference only)
        
    Returns:
        Dictionary containing statistics (seconds as floats for precision)
    """
    # Initialize counters as floats
    present_seconds = 0.0
    away_seconds = 0.0
    gadget_seconds = 0.0
    screen_distraction_seconds = 0.0
    paused_seconds = 0.0
    
    # Sum up durations by event type
    # Truncate each to int before summing so summary = sum of displayed log values
    for event in events:
        raw_duration = float(event.get("duration_seconds", 0))
        # Truncate to match what will be displayed in logs
        duration = float(int(raw_duration))
        event_type = event.get("type")
        
        if event_type == config.EVENT_PRESENT:
            present_seconds += duration
        elif event_type == config.EVENT_AWAY:
            away_seconds += duration
        elif event_type == config.EVENT_GADGET_SUSPECTED:
            gadget_seconds += duration
        elif event_type == config.EVENT_SCREEN_DISTRACTION:
            screen_distraction_seconds += duration
        elif event_type == config.EVENT_PAUSED:
            paused_seconds += duration
    
    # Calculate derived values
    # Screen distraction counts as active time (user is at desk, just distracted)
    active_seconds = present_seconds + away_seconds + gadget_seconds + screen_distraction_seconds
    distracted_seconds = away_seconds + gadget_seconds + screen_distraction_seconds
    total_seconds = active_seconds + paused_seconds
    
    # Consolidate events for timeline (keeps float precision)
    consolidated = consolidate_events(events)
    
    # Return float seconds - truncation happens at PDF display time
    return {
        "total_seconds": total_seconds,
        "present_seconds": present_seconds,
        "away_seconds": away_seconds,
        "gadget_seconds": gadget_seconds,
        "screen_distraction_seconds": screen_distraction_seconds,
        "paused_seconds": paused_seconds,
        "active_seconds": active_seconds,
        "distracted_seconds": distracted_seconds,
        # Legacy minute values for backward compatibility
        "total_minutes": total_seconds / 60.0,
        "focused_minutes": present_seconds / 60.0,
        "away_minutes": away_seconds / 60.0,
        "gadget_minutes": gadget_seconds / 60.0,
        "screen_distraction_minutes": screen_distraction_seconds / 60.0,
        "paused_minutes": paused_seconds / 60.0,
        "present_minutes": present_seconds / 60.0,
        "events": consolidated
    }


def consolidate_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Consolidate consecutive similar events and format for timeline.
    
    This merges consecutive events of the same type to reduce noise
    and creates a cleaner timeline view.
    
    Keeps float precision - truncation happens at PDF display time.
    Truncates each event to int BEFORE summing so consolidated totals
    match what individual displayed events would sum to.
    
    Args:
        events: List of raw event dictionaries
        
    Returns:
        List of consolidated events with readable format
    """
    if not events:
        return []
    
    consolidated = []
    current_event = None
    
    for event in events:
        event_type = event.get("type")
        start_time = event.get("start")
        end_time = event.get("end")
        raw_duration = float(event.get("duration_seconds", 0))
        # Truncate to int then back to float - ensures sum matches displayed values
        duration = float(int(raw_duration))
        
        # If this is the same type as current, extend the current event
        if current_event and current_event["type"] == event_type:
            current_event["end"] = end_time
            current_event["duration_seconds"] += duration
        else:
            # Save previous event if exists
            if current_event:
                consolidated.append(_format_event(current_event))
            
            # Start new event
            current_event = {
                "type": event_type,
                "start": start_time,
                "end": end_time,
                "duration_seconds": duration
            }
    
    # Don't forget the last event
    if current_event:
        consolidated.append(_format_event(current_event))
    
    return consolidated


def _format_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format an event for display with human-readable times and durations.
    
    Keeps float precision - truncation to int happens at PDF display time.
    
    Args:
        event: Event dictionary with start, end, type, and duration
        
    Returns:
        Formatted event dictionary with duration_seconds as float
    """
    start = datetime.fromisoformat(event["start"])
    end = datetime.fromisoformat(event["end"])
    duration_seconds = float(event["duration_seconds"])
    
    # Create readable event type labels
    type_labels = {
        config.EVENT_PRESENT: "Focused",
        config.EVENT_AWAY: "Away",
        config.EVENT_GADGET_SUSPECTED: "Gadget Usage",
        config.EVENT_SCREEN_DISTRACTION: "Screen Distraction",
        config.EVENT_PAUSED: "Paused"
    }
    
    return {
        "type": event["type"],
        "type_label": type_labels.get(event["type"], event["type"]),
        "start": start.strftime("%I:%M %p"),
        "end": end.strftime("%I:%M %p"),
        "duration_seconds": duration_seconds,  # Float precision
        "duration_minutes": duration_seconds / 60.0  # For backward compatibility
    }


def get_focus_percentage(stats: Dict[str, Any]) -> float:
    """
    Calculate focus percentage from statistics.
    
    Focus rate = present / active_time, where active_time = present + away + gadget + screen_distraction.
    Paused time is completely excluded from both numerator and denominator.
    This ensures the focus rate is always between 0% and 100%.
    
    Args:
        stats: Statistics dictionary from compute_statistics
        
    Returns:
        Focus percentage (0-100), never exceeds 100%
    """
    # Use float seconds from stats
    if "active_seconds" in stats:
        active_time = float(stats["active_seconds"])
        present_time = float(stats["present_seconds"])
    else:
        # Legacy fallback (includes screen_distraction if present)
        screen_distraction = stats.get("screen_distraction_minutes", 0)
        active_time = (stats.get("present_minutes", 0) + 
                       stats.get("away_minutes", 0) + 
                       stats.get("gadget_minutes", 0) +
                       screen_distraction) * 60.0
        present_time = stats.get("present_minutes", 0) * 60.0
    
    if active_time <= 0:
        return 0.0
    
    # Focus rate = present / active (guaranteed 0-100%)
    focus_pct = (present_time / active_time) * 100.0
    
    # Clamp to 0-100 for safety
    return min(100.0, max(0.0, focus_pct))


def generate_summary_text(stats: Dict[str, Any]) -> str:
    """
    Generate a simple text summary of the session.
    
    This is a fallback summary in case OpenAI API is not available.
    Uses raw seconds and converts to display format at the end.
    
    Args:
        stats: Statistics dictionary from compute_statistics
        
    Returns:
        Human-readable summary string
    """
    # Get values in seconds (new format) or convert from minutes (legacy)
    if "active_seconds" in stats:
        active_secs = stats["active_seconds"]
        present_secs = stats["present_seconds"]
        away_secs = stats["away_seconds"]
        gadget_secs = stats["gadget_seconds"]
        screen_distraction_secs = stats.get("screen_distraction_seconds", 0)
        paused_secs = stats["paused_seconds"]
    else:
        present_secs = stats.get("present_minutes", 0) * 60
        away_secs = stats.get("away_minutes", 0) * 60
        gadget_secs = stats.get("gadget_minutes", 0) * 60
        screen_distraction_secs = stats.get("screen_distraction_minutes", 0) * 60
        paused_secs = stats.get("paused_minutes", 0) * 60
        active_secs = present_secs + away_secs + gadget_secs + screen_distraction_secs
    
    focus_pct = get_focus_percentage(stats)
    
    # Format active time as duration
    total_secs = int(active_secs + paused_secs)
    hours = total_secs // 3600
    minutes = (total_secs % 3600) // 60
    
    if hours > 0:
        duration_str = f"{hours}h {minutes}m"
    else:
        duration_str = f"{minutes}m"
    
    # Format individual times
    def fmt_mins(secs):
        return f"{secs / 60:.1f}"
    
    summary = f"""Session Summary:
Total Duration: {duration_str}
Focused Time: {fmt_mins(present_secs)} minutes ({focus_pct:.1f}%)
Away Time: {fmt_mins(away_secs)} minutes
Gadget Usage: {fmt_mins(gadget_secs)} minutes
"""
    
    # Only show screen distraction time if > 0
    if screen_distraction_secs > 0:
        summary += f"Screen Distraction: {fmt_mins(screen_distraction_secs)} minutes\n"
    
    # Only show paused time if > 0
    if paused_secs > 0:
        summary += f"Paused Time: {fmt_mins(paused_secs)} minutes\n"
    
    summary += "\n"
    
    # Add simple observation
    if focus_pct >= 80:
        summary += "Excellent focus! You stayed on task for most of the session."
    elif focus_pct >= 60:
        summary += "Good session! You maintained decent focus with some breaks."
    elif focus_pct >= 40:
        summary += "Fair session. Consider minimizing distractions for better focus."
    else:
        summary += "This session had many interruptions. Try to find a quieter space."
    
    return summary

