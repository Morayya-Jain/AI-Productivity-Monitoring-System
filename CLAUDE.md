# Gavin AI - Agent Quick Reference

**TL;DR**: Python focus tracker using OpenAI Vision API + screen monitoring to detect present/away/gadget/screen_distraction/paused states. Generates PDF reports.

## 📁 Key Files

| File | Purpose |
|------|---------|
| `config.py` | **ALL constants** (models, FPS, thresholds, modes) |
| `camera/vision_detector.py` | Camera detection logic (`analyze_frame()`) |
| `screen/window_detector.py` | Screen monitoring (Chrome URLs, window titles) |
| `screen/blocklist.py` | Distracting sites/apps blocklist management |
| `tracking/analytics.py` | **Stats computation - MATH MUST ADD UP** |
| `tracking/session.py` | Event logging, state changes |
| `reporting/pdf_report.py` | PDF generation (~/Downloads/) |
| `gui/app.py` | Desktop GUI (tkinter) - main application |

*Ignore: `detection.py`, `phone_detector.py` (legacy)*

## ⚠️ Critical Rules

1. **Math Must Add Up**: `present + away + gadget + screen_distraction + paused = total` in `analytics.py`
2. **AI-Only Detection** (Camera): OpenAI Vision API only (~$0.06-0.12/min)
3. **Screen Detection**: Local pattern matching first, AI fallback optional
4. **Time Format**: Use `_format_time()` → "1m 30s" not "1.5 minutes"

## 📊 Event Types

- `present`: At desk, focused
- `away`: Not visible or far from desk
- `gadget_suspected`: Actively using phone/tablet/controller/TV
- `screen_distraction`: Distracting website/app detected (YouTube, Netflix, etc.)
- `paused`: User manually paused session

## 🖥️ Monitoring Modes

- `camera_only`: Default - camera detection only (backward compatible)
- `screen_only`: Screen monitoring only (no API calls for camera)
- `both`: Camera + screen monitoring (combined detection)

## ⏸️ Pause & Alerts

- Pause: Timer freezes, no API calls. Focus rate = present/(total-paused)
- Unfocused alerts: 20s → 60s → 120s, then stops until refocus

## 🔧 Key Constants (config.py)

```python
DETECTION_FPS = 0.33              # ~3s between camera API calls
SCREEN_CHECK_INTERVAL = 3         # 3s between screen checks (no API)
MODE_CAMERA_ONLY, MODE_SCREEN_ONLY, MODE_BOTH  # Monitoring modes
OPENAI_VISION_MODEL = "gpt-4o-mini"
```

## 🐛 Common Issues

| Issue | Fix |
|-------|-----|
| "Vision API Error: Expecting value" | JSON parsing failed. Check markdown wrapping |
| "Statistics don't add up" | Verify math in `analytics.py` |
| "Gadget not detected" | Must be actively in use with person looking at it |

## 🚫 What NOT to Do

- ❌ Fallback detection (AI-only) | ❌ Save frames to disk (privacy) | ❌ Increase API frequency
- ❌ Decimal minutes | ❌ Stats that don't sum | ❌ Run multiple instances

## 🔐 Setup & Test

```bash
# Required: .env with OPENAI_API_KEY=sk-...
source venv/bin/activate
python3 main.py  # GUI launches, check ~/Downloads/ for PDF
python3 -m unittest tests.test_session tests.test_analytics
```

## 📁 Data Files

- `data/focus_statements.json` - **REQUIRED** - PDF feedback templates
- `data/blocklist.json` - Screen monitoring blocklist (auto-created)
- `data/usage_data.json` - Usage tracking (gitignored)

## 🔄 Add New Detection Type

1. Add to `config.py` → 2. Handle in `session.py` → 3. Stats in `analytics.py` → 4. PDF in `pdf_report.py` → 5. GUI status color in `app.py`

## 🖥️ Screen Monitoring

- Blocklist categories: Social Media, Video Streaming, Gaming (toggle in settings)
- Custom patterns: Add URLs/app names in Blocklist Settings
- Chrome URL detection: macOS (AppleScript), Windows (pywin32)
- AI fallback: Optional, only when local detection inconclusive

## 📝 Code Standards

Type hints required • Docstrings • `pathlib.Path` • Python 3.9+ • `logger.info()` internal, `print()` user-facing

**Privacy**: Camera frames → OpenAI (30-day retention) → deleted. No video saved locally.
