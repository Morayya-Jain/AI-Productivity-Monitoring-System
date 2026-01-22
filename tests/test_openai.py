#!/usr/bin/env python3
"""
Test script to verify OpenAI API integration.

Note: This test requires the ai.summariser module which was deprecated.
The summarization functionality is now handled inline by the PDF report
and analytics modules. This test is skipped unless the module exists.

To test OpenAI Vision API integration, use test_gadget_detection.py instead.
"""

import unittest
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# Check if summariser module exists
def _summariser_available():
    """Check if the deprecated summariser module is available."""
    try:
        import importlib
        importlib.import_module("ai.summariser")
        return True
    except ImportError:
        return False


SUMMARISER_AVAILABLE = _summariser_available()


@unittest.skipUnless(SUMMARISER_AVAILABLE, "ai.summariser module not available (deprecated)")
class TestOpenAISummariser(unittest.TestCase):
    """Test cases for the SessionSummariser class (if available)."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Import dynamically to avoid static analysis errors
        import importlib
        summariser_module = importlib.import_module("ai.summariser")
        SessionSummariser = getattr(summariser_module, "SessionSummariser")
        
        from dotenv import load_dotenv
        load_dotenv()
        
        self.api_key = os.getenv("OPENAI_API_KEY")
        if self.api_key:
            self.summariser = SessionSummariser()
        else:
            self.summariser = None
    
    @unittest.skipUnless(os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY not set")
    def test_summariser_initialization(self):
        """Test that SessionSummariser initializes correctly."""
        self.assertIsNotNone(self.summariser)
        self.assertIsNotNone(self.summariser.client)
    
    @unittest.skipUnless(os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY not set")
    def test_generate_summary(self):
        """Test summary generation with sample data."""
        test_stats = {
            "total_minutes": 30.0,
            "focused_minutes": 22.0,
            "away_minutes": 5.0,
            "gadget_minutes": 3.0,
            "events": [
                {
                    "type": "present",
                    "type_label": "Focused",
                    "start": "02:00 PM",
                    "end": "02:22 PM",
                    "duration_minutes": 22.0
                },
                {
                    "type": "away",
                    "type_label": "Away",
                    "start": "02:22 PM",
                    "end": "02:27 PM",
                    "duration_minutes": 5.0
                },
                {
                    "type": "gadget_suspected",
                    "type_label": "Gadget Usage",
                    "start": "02:27 PM",
                    "end": "02:30 PM",
                    "duration_minutes": 3.0
                }
            ]
        }
        
        result = self.summariser.generate_summary(test_stats)
        
        self.assertIn("success", result)
        self.assertIn("summary", result)
        self.assertIn("suggestions", result)
        
        if result["success"]:
            self.assertIsInstance(result["summary"], str)
            self.assertIsInstance(result["suggestions"], list)


if __name__ == "__main__":
    # When run directly, provide helpful information
    if not SUMMARISER_AVAILABLE:
        print("═══════════════════════════════════════════════════════")
        print("⚠️  SKIPPED: ai.summariser module not found")
        print("═══════════════════════════════════════════════════════\n")
        print("The SessionSummariser class has been deprecated.")
        print("Summarization is now handled by:")
        print("  - tracking/analytics.py: generate_summary_text()")
        print("  - reporting/pdf_report.py: PDF generation with AI insights")
        print("\nTo test OpenAI Vision API, run:")
        print("  python tests/test_gadget_detection.py")
        sys.exit(0)
    
    unittest.main()
