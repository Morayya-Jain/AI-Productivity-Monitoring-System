"""PDF report generation using ReportLab."""

import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    Frame,
    PageTemplate
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfgen import canvas

import config

logger = logging.getLogger(__name__)


def _add_gradient_background(canvas_obj, doc):
    """
    Add a subtle gradient background to the page.
    
    Args:
        canvas_obj: ReportLab canvas object
        doc: Document object
    """
    canvas_obj.saveState()
    
    # Create a smooth gradient from light blue to white
    # Fades from top to middle of page
    width, height = letter
    
    # Use a slightly darker blue for better visibility
    gradient_color = colors.HexColor('#D6EAF8')  # Darker than #E8F4F8 but still subtle
    
    # Create smooth gradient with many steps for seamless blend
    # Goes from top to middle of page (50% of height)
    num_steps = 50  # More steps = smoother gradient
    gradient_height = height * 0.5  # Gradient covers top half of page
    step_height = gradient_height / num_steps
    
    for i in range(num_steps):
        # Calculate alpha that goes from full color to completely transparent
        alpha = 1 - (i / num_steps)
        
        # Create color with decreasing opacity
        color = colors.Color(
            gradient_color.red,
            gradient_color.green,
            gradient_color.blue,
            alpha=alpha * 0.7  # Increased from 0.6 to 0.7 for more visibility
        )
        
        canvas_obj.setFillColor(color)
        y_pos = height - (i * step_height)
        canvas_obj.rect(0, y_pos - step_height, width, step_height, fill=1, stroke=0)
    
    canvas_obj.restoreState()


def _add_header(canvas_obj, doc):
    """
    Add header with Gavin AI logo text to each page.
    
    Args:
        canvas_obj: ReportLab canvas object
        doc: Document object
    """
    canvas_obj.saveState()
    width, height = letter
    
    # Add "GAVIN AI" text logo in top right
    canvas_obj.setFont('Times-Bold', 14)
    canvas_obj.setFillColor(colors.HexColor('#4A90E2'))
    canvas_obj.drawRightString(width - 50, height - 40, "GAVIN AI")
    
    canvas_obj.restoreState()


def _create_page_template(canvas_obj, doc):
    """
    Create custom page template with gradient and header.
    
    Args:
        canvas_obj: ReportLab canvas object
        doc: Document object
    """
    _add_gradient_background(canvas_obj, doc)
    _add_header(canvas_obj, doc)


def _format_time(minutes: float) -> str:
    """
    Format time in a human-readable way.
    
    Args:
        minutes: Time in minutes (can be fractional)
        
    Returns:
        Formatted string like "1m 30s" or "45s" or "2h 15m"
        Values less than 1 minute show in seconds only
        Omits .0 decimals (e.g., "45.0%" becomes "45%")
    """
    total_seconds = int(minutes * 60)
    
    # Less than 1 minute - show seconds only
    if total_seconds < 60:
        return f"{total_seconds}s"
    
    hours = total_seconds // 3600
    remaining_seconds = total_seconds % 3600
    mins = remaining_seconds // 60
    secs = remaining_seconds % 60
    
    if hours > 0:
        if secs > 0:
            return f"{hours}h {mins}m {secs}s"
        else:
            return f"{hours}h {mins}m"
    else:
        if secs > 0:
            return f"{mins}m {secs}s"
        else:
            return f"{mins}m"


def generate_report(
    stats: Dict[str, Any],
    summary_data: Dict[str, Any],
    session_id: str,
    start_time: datetime,
    end_time: Optional[datetime] = None,
    output_dir: Optional[Path] = None
) -> Path:
    """
    Generate a PDF report from session statistics and AI summary.
    
    Args:
        stats: Statistics dictionary from analytics.compute_statistics()
        summary_data: Summary and suggestions from AI summariser
        session_id: Unique session identifier
        start_time: Session start time
        end_time: Session end time (optional)
        output_dir: Output directory (defaults to config.REPORTS_DIR)
        
    Returns:
        Path to the generated PDF file
    """
    if output_dir is None:
        output_dir = config.REPORTS_DIR
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    filename = f"{session_id}.pdf"
    filepath = output_dir / filename
    
    # Create PDF document with custom template
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=letter,
        rightMargin=60,
        leftMargin=60,
        topMargin=80,
        bottomMargin=60
    )
    
    # Build the story (content)
    story = []
    styles = getSampleStyleSheet()
    
    # Define Georgia font (Times-Roman is similar and built-in to ReportLab)
    # Georgia isn't built-in, but Times-Roman is elegant and serif like Georgia
    
    # Custom styles with Georgia-like font (Times-Roman)
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName='Times-Bold',
        fontSize=28,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=20,
        spaceBefore=10,
        alignment=TA_LEFT,
        leading=34
    )
    
    subtitle_style = ParagraphStyle(
        'Subtitle',
        parent=styles['Normal'],
        fontName='Times-Italic',
        fontSize=12,
        textColor=colors.HexColor('#7F8C8D'),
        spaceAfter=30,
        alignment=TA_LEFT
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontName='Times-Bold',
        fontSize=18,
        textColor=colors.HexColor('#34495E'),
        spaceAfter=15,
        spaceBefore=20,
        alignment=TA_LEFT,
        leading=22
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontName='Times-Roman',
        fontSize=12,  # Increased from 11 to 12
        textColor=colors.HexColor('#2C3E50'),
        leading=17,  # Adjusted leading proportionally
        spaceAfter=8
    )
    
    # Title - clean and elegant without emoji
    story.append(Paragraph("Study Session Report", title_style))
    
    # Session metadata as subtitle with date and time range
    date_str = start_time.strftime("%B %d, %Y")
    start_time_str = start_time.strftime("%I:%M")
    
    # Build time range string
    if end_time:
        end_time_str = end_time.strftime("%I:%M%p")  # No space before AM/PM
        # Remove leading zero from hours if present
        start_time_str = start_time_str.lstrip('0').replace(' ', '')
        end_time_str = end_time_str.lstrip('0').replace(' ', '')
        metadata = f"{date_str} from {start_time_str} - {end_time_str}"
    else:
        start_time_str = start_time.strftime("%I:%M%p").lstrip('0').replace(' ', '')  # No space before AM/PM
        metadata = f"{date_str} at {start_time_str}"
    
    story.append(Paragraph(metadata, subtitle_style))
    
    # Statistics section
    story.append(Paragraph("Session Statistics", heading_style))
    
    # Create statistics table with modern, clean design
    stats_data = [
        ['Metric', 'Value'],
        ['Total Duration', _format_time(stats['total_minutes'])],
        ['Present at Desk', _format_time(stats['present_minutes'])],
        ['Away from Desk', _format_time(stats['away_minutes'])],
        ['Phone Usage', _format_time(stats['phone_minutes'])],
    ]
    
    # Calculate focus percentage (present time / total time)
    # Note: Phone time is separate from present time, not subtracted from it
    focus_pct = (stats['present_minutes'] / stats['total_minutes'] * 100) if stats['total_minutes'] > 0 else 0
    # Format percentage without .0 decimal
    focus_pct_str = f"{int(focus_pct)}%" if focus_pct == int(focus_pct) else f"{focus_pct:.1f}%"
    stats_data.append(['Focus Rate', focus_pct_str])
    
    stats_table = Table(stats_data, colWidths=[3.0 * inch, 3.0 * inch])  # Total 6.0 inches to match timeline table
    stats_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A90E2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 13),  # Increased from 12 to 13
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        # Data rows
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFB')),
        ('FONTNAME', (0, 1), (0, -1), 'Times-Roman'),
        ('FONTNAME', (1, 1), (1, -1), 'Times-Bold'),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('TOPPADDING', (0, 1), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
        ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#4A90E2')),
        ('LINEBELOW', (0, 1), (-1, -2), 0.5, colors.HexColor('#E0E6ED')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#2C3E50')),
    ]))
    
    story.append(stats_table)
    story.append(Spacer(1, 0.3 * inch))  # Reduced from 0.4 to 0.3
    
    # Timeline section
    story.append(Paragraph("Session Timeline", heading_style))
    
    events = stats.get('events', [])
    if events:
        # Limit to most significant events for readability
        display_events = events[:8]
        
        timeline_data = [['Time', 'Activity', 'Duration']]
        for event in display_events:
            timeline_data.append([
                f"{event['start']} - {event['end']}",
                event['type_label'],
                _format_time(event['duration_minutes'])
            ])
        
        if len(events) > 8:
            timeline_data.append(['...', f'{len(events) - 8} more events', '...'])
        
        timeline_table = Table(timeline_data, colWidths=[2.4 * inch, 2.2 * inch, 1.4 * inch])
        timeline_table.setStyle(TableStyle([
            # Header - now matches first table color
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4A90E2')),  # Changed from #5DADE2 to match first table
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),  # Increased from 11 to 12
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            # Data rows
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFB')),
            ('FONTNAME', (0, 1), (1, -1), 'Times-Roman'),  # Time and Activity columns
            ('FONTNAME', (2, 1), (2, -1), 'Times-Bold'),  # Duration column bold
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
            ('LINEBELOW', (0, 0), (-1, 0), 2, colors.HexColor('#4A90E2')),  # Changed to match
            ('LINEBELOW', (0, 1), (-1, -2), 0.5, colors.HexColor('#E0E6ED')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.HexColor('#2C3E50')),
        ]))
        
        story.append(timeline_table)
    else:
        story.append(Paragraph("No events recorded.", body_style))
    
    story.append(Spacer(1, 0.25 * inch))  # Reduced from 0.4 to 0.25
    
    # AI Summary section - keep together to prevent page break
    heading_style_keepwithnext = ParagraphStyle(
        'HeadingKeepWithNext',
        parent=heading_style,
        keepWithNext=True  # Prevents heading from separating from content
    )
    
    story.append(Paragraph("Session Analysis", heading_style_keepwithnext))
    
    summary_text = summary_data.get('summary', 'No summary available.')
    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 0.2 * inch))  # Reduced from 0.25 to 0.2
    
    # Suggestions section
    story.append(Paragraph("Key Takeaways", heading_style_keepwithnext))
    
    suggestions = summary_data.get('suggestions', [])
    if suggestions:
        for i, suggestion in enumerate(suggestions, 1):
            bullet_text = f"<b>{i}.</b> {suggestion}"
            story.append(Paragraph(bullet_text, body_style))
            story.append(Spacer(1, 0.12 * inch))
    else:
        story.append(Paragraph("No suggestions available.", body_style))
    
    story.append(Spacer(1, 0.5 * inch))
    
    # Footer - elegant and minimal
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontName='Times-Italic',
        fontSize=9,
        textColor=colors.HexColor('#95A5A6'),
        alignment=TA_CENTER
    )
    
    footer_text = "Generated by Gavin AI"
    story.append(Paragraph(footer_text, footer_style))
    
    # Build PDF with custom page template
    try:
        doc.build(story, onFirstPage=_create_page_template, onLaterPages=_create_page_template)
        logger.info(f"PDF report generated: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        raise

