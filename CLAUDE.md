# Activity Tracker MVP

## Session Start Instructions
When starting a new session on this project:
1. Run `git status`, `git diff`, and `git log --oneline -10` to understand recent changes
2. Check for any TODO comments: `grep -r "TODO" tracker/`
3. Review the Decision Log below for context
4. Inform user that you've reviewed recent changes and ask what to work on next

**IMPORTANT:** After every task, check if CLAUDE.md needs to be updated

## Project Goal
Linux background service that captures screenshots at intervals, stores metadata in SQLite, and provides a simple web viewer.

## Tech Stack
- Python 3.11+
- mss for screenshots
- SQLite for metadata
- Flask for web viewer
- WebP for image compression
- pytest for testing

## Architecture
- Capture daemon: runs via systemd user service
- Storage: ~/activity-tracker-data/
  - screenshots/YYYY/MM/DD/{timestamp}_{hash}.webp
  - activity.db (SQLite)
- Web viewer: localhost:5000

## Key Constraints
- X11 only (Wayland not supported - requires xdotool + xrandr)
- Configurable capture intervals (default 30 seconds)
- OCR via Tesseract (optional, for AI summarization)
- Multi-monitor support (captures active monitor only)

## File Structure
```
activity-tracker/
├── tracker/
│   ├── __init__.py
│   ├── capture.py           # Screenshot capture logic
│   ├── storage.py           # SQLite + filesystem management
│   ├── daemon.py            # Background service daemon
│   ├── config.py            # YAML-based configuration management
│   ├── analytics.py         # Activity analytics and statistics
│   ├── vision.py            # AI summarization (OCR + LLM)
│   ├── summarizer_worker.py # Background worker for threshold-based summarization
│   ├── afk.py               # AFK detection via pynput
│   ├── sessions.py          # Session management
│   ├── timeparser.py        # Natural language time range parser
│   ├── reports.py           # Report generator with analytics
│   ├── report_export.py     # Export reports to Markdown/HTML/PDF/JSON
│   └── window_watcher.py    # Real-time window focus tracking
├── web/
│   ├── app.py               # Flask application with REST API
│   └── templates/
│       ├── timeline.html    # Timeline view with AI summaries
│       ├── analytics.html   # Analytics dashboard
│       ├── reports.html     # Report generation UI
│       └── settings.html    # Configuration UI
├── tests/                   # Pytest test suite
│   ├── conftest.py          # Test fixtures
│   ├── test_capture.py      # Capture functionality tests
│   ├── test_storage.py      # Storage CRUD tests
│   └── test_dhash.py        # Hash comparison tests
├── scripts/
│   ├── install.sh           # Systemd service setup (auto-enables web + summarization)
│   └── summarize_activity.py  # CLI for generating summaries
├── requirements.txt
├── README.md                # Project documentation
└── CLAUDE.md
```

## Decision Log
- **2025-11-27**: Added comprehensive test suite with pytest (85% coverage target)
- **2025-11-27**: Added full docstrings to all modules following PEP 257
- **2025-11-27**: Created README.md with installation and usage instructions
- **2025-11-27**: Identified 13 edge cases requiring attention (see TODO comments)

### 2024-12-02 - Phase 1: Timeline + Analytics
- Building rich timeline UI with calendar heatmap + hourly drill-down
- Full analytics dashboard with charts (using Chart.js)
- New routes: /timeline, /analytics, /api/activity-data
- Keeping existing day view, timeline is additive
- Stack: Flask + Jinja2 + Chart.js + vanilla JS (no React)

### 2025-12-08 - Phase 2: Session-Based Tracking
- Implemented AFK detection using pynput (keyboard/mouse monitoring)
- Session management: automatic session start/end on AFK transitions
- Screenshots linked to sessions via junction table
- Session summaries with context continuity (previous session context)
- OCR caching per unique window title within sessions
- Smart session resume on daemon restart (checks if within AFK timeout)
- API request details stored for debugging (prompt_text column)
- Info icons added throughout UI with tooltips
- Live counts for ongoing sessions (calculated from session_screenshots)
- Generate button shows loading feedback immediately
- Window geometry detection and cropping for improved OCR/LLM accuracy
  - Captures focused window bounds using xdotool
  - Stores window geometry (x, y, width, height) in database
  - Creates cropped screenshots on-demand for OCR and summarization
  - Cached as {original}_crop.webp files for performance
  - Handles edge cases: fullscreen apps, partially off-screen windows, missing geometry
  - Multi-monitor support via geometry coordinates
- Multi-monitor support with intelligent capture
  - Detects connected monitors using xrandr
  - Captures only the monitor with the focused window
  - Stores monitor metadata (name, width, height) in database
  - Window geometry coordinates relative to captured monitor
  - Automatic fallback to primary monitor when no focused window
  - 60-second cache refresh for hotplug support
  - Handles edge cases: window spanning monitors, xrandr unavailable, monitor hotplug
  - Significant file size reduction (e.g., 5K instead of dual 10K virtual screen)

### 2025-12-09 - Phase 3: Threshold-Based Summarization
- Replaced session-based summarization with threshold-based approach
- Summaries triggered after every N screenshots (configurable, default: 10)
- Background SummarizerWorker with queue-based processing
- New threshold_summaries table with version history support
- Regenerate summaries with different models/settings
- Timeline UI shows AI summaries panel with regenerate/history/delete actions
- Settings page loads Ollama models dynamically from API
- Model changes take effect immediately (no daemon restart needed)
- Install script now auto-enables web server and summarization (no prompts)

### 2025-12-09 - Phase 4: Report Generation
- Natural language time range parser (timeparser.py)
  - Supports: "today", "yesterday", "last week", "this month", "past 3 days", etc.
  - Weekday names: "monday", "last friday"
  - Date ranges: "2025-12-01 to 2025-12-07"
- Report generator (reports.py) with three report types:
  - Summary: High-level executive summary with analytics
  - Detailed: Day-by-day breakdown
  - Standup: Brief bullet points for standup meetings
- Analytics computation: app usage, window usage, activity by hour/day
- Export functionality (report_export.py):
  - Markdown with screenshot references
  - Standalone HTML with embedded images
  - PDF via weasyprint (optional)
  - JSON for programmatic access
- Reports page UI with quick presets and custom time ranges
- API endpoints: /api/reports/generate, /api/reports/export, /api/reports/presets
- Reports stored in ~/activity-tracker-data/reports/
- Default model changed to gemma3:12b-it-qat (better balance of speed/quality)
- Added 1h keepalive to Ollama API calls for faster subsequent responses

### 2025-12-09 - Phase 5: Window Focus Tracking
- Real-time window focus tracking (window_watcher.py)
  - WindowWatcher class with polling loop and callback support
  - WindowFocusEvent dataclass with duration tracking
  - Uses xdotool/xprop for X11 window detection
- Focus-aware screenshot capture in daemon
  - Stability threshold: wait for focus to settle before capture
  - Max interval multiplier: force capture after extended time
  - Skip transient windows (notifications, popups, tooltips)
  - Configurable via tracking section in config.yaml
- Focus events stored in window_focus_events table
  - Links to sessions for context
  - Duration and app/window tracking
- Focus context in AI summarization
  - Time breakdown by app/window in prompts
  - Context switches counted
  - Helps LLM understand work patterns
- Focus Analytics API endpoints:
  - /api/analytics/focus/<date> - Daily focus analytics
  - /api/analytics/focus/timeline - Timeline visualization data
  - /api/analytics/focus/summary - Summary for reports
- Analytics dashboard enhanced with Focus Tracking section:
  - Tracked time, context switches, longest focus metrics
  - Visual timeline with app color coding
  - Top windows table by time spent
  - Deep work sessions list (10+ min focused)

### 2025-12-09 - Phase 6: App/Window Focus Context (Simplified)
- **Simplified approach**: Instead of complex project detection, we pass raw app/window
  usage data directly to the LLM and let it interpret activities
- Focus events already capture app_name, window_title, duration_seconds
- Summarization now sends:
  - Time breakdown by app/window (aggregated from focus events)
  - Context switches count
  - Screenshots (sampled based on focus time)
  - OCR text from unique windows
- LLM prompt guidance:
  - Focus on where most time was spent
  - Use specific project names visible in content
  - Do NOT assume different apps/windows are related unless clearly same project
- Backward compatible: `project` column exists but not populated for new summaries
- Focus-weighted screenshot sampling for LLM
  - Sampling reflects focus duration distribution (80% terminal time → 80% terminal screenshots)
  - Configurable via summarization section:
    - sample_interval_minutes: target interval between samples (default: 10)
    - max_samples: maximum screenshots per batch (default: 10)
    - focus_weighted_sampling: enable weighted sampling (default: true)
  - Falls back to uniform sampling when focus data unavailable
  - Sorted chronologically after weighting for natural flow
- Summarization mode selection
  - Replaced ocr_enabled toggle with summarization_mode dropdown
  - Three modes: "ocr_and_screenshots", "screenshots_only", "ocr_only"
  - Allows LLM to work with just text or just images
- Ollama host configurable from settings page
- Report generation uses configured model (not hardcoded)

### 2025-12-10 - Phase 7: Simplified Summarization Settings + Thumbnails
- **Simplified AI Summarization UI** - Reduced from 10 confusing settings to 4 clear controls:
  - Enable Summarization (toggle)
  - Model (dropdown with Ollama models)
  - Summary Frequency (time-based: Every 5/15/30/60 min)
  - Summary Quality (presets: Quick/Balanced/Thorough)
  - Content to Include (multi-select checkboxes):
    - Window titles + duration (focus context)
    - Screenshots (visual context)
    - OCR text (extracted text)
- **Quality Presets** - Auto-configure underlying settings:
  - Quick: 5 samples, no previous context, no focus-weighting
  - Balanced: 10 samples, with context, focus-weighted
  - Thorough: 15 samples, with context, focus-weighted
- **Collapsible Advanced Settings** showing:
  - Ollama Host, Crop to Window
  - Underlying settings (update when preset changes)
  - Dynamic prompt template preview
- **Prompt Template Preview** - Shows exact prompt that will be sent to LLM:
  - Updates in real-time when content options change
  - Shows which sections are included/excluded
  - Warning if no content options selected
- **Config changes** (config.py):
  - Added: frequency_minutes, quality_preset
  - Added: include_focus_context, include_screenshots, include_ocr (multi-select)
  - Kept underlying settings for backward compatibility
- **Thumbnail generation** for faster timeline loading:
  - 200px width, WebP format, 75% quality (~4KB each vs ~500KB originals)
  - Stored in ~/activity-tracker-data/thumbnails/
  - Migration script: scripts/generate_thumbnails.py
  - On-demand generation for new screenshots
- **API Request display** in summary details:
  - prompt_text column in threshold_summaries table
  - Shows exact prompt sent to Ollama for debugging
- **Bug fixes**:
  - Fixed daily summary exceeding Ollama context window (limited to 20 summaries, 150 chars each)
  - Fixed loading spinner not clearing in timeline
  - Fixed 'summarization_mode' attribute error after refactor
  - **Fixed summarization triggering** - Now uses actual duration-based triggering:
    - Checks time elapsed since last summary, not screenshot count
    - frequency_minutes setting now works as expected (e.g., 15 min = summary every 15 minutes)
    - Old trigger_threshold was never computed from frequency_minutes (hardcoded to 30)
  - **Fixed focus tracking duration** in AI prompts:
    - Focus events now clipped to project-specific time range (not batch range)
    - Previously: batch covers 8:00-12:00, project A only 10:00-11:00, but durations clipped to 8:00-12:00
    - Fix: `_summarize_project_batch()` re-clips focus durations to project screenshot time range
    - Added get_focus_events_overlapping_range() to capture events spanning the range
  - **Fixed frequency_minutes not working** - summaries triggered every 2 min instead of 15 min:
    - Frequency check was using `end_time` (screenshot timestamp) instead of `created_at` (when job ran)
    - When summarizing old screenshots, `end_time` could be hours ago, causing immediate re-trigger
    - Fix: Use `created_at` field in `check_and_queue()` to track when summarization job last ran

### 2025-12-11 - Phase 8: Simplifications & Bug Fixes
- **Removed project detection complexity**:
  - Removed `project_detector.py` import from summarizer_worker
  - No longer grouping screenshots by detected project before summarization
  - LLM receives raw app/window usage breakdown and interprets activities itself
  - Simpler code, more transparent (LLM sees what we see)
  - Added prompt guidance: "Do NOT assume different apps/windows are related unless clearly same project"
- **Settings page improvements**:
  - Renamed "Window titles + duration" to "App/window usage breakdown" with clearer description
  - Updated prompt template preview to show realistic example of focus data
  - Fixed "You have unsaved changes" showing on page load (was calling trackChange during init)
- **Timeline timezone fix**:
  - Fixed timeline showing wrong date (e.g., Dec 12 instead of Dec 11 at 9 PM local time)
  - Problem: `toISOString().split('T')[0]` returns UTC date, not local
  - Solution: Added `getLocalDateString(date)` helper using local year/month/day
  - Fixed all 5 instances: initial load, today link, keyboard shortcut, day navigation, calendar highlight
  - Removed duplicate dead code function
- **Code cleanup**:
  - Removed `_summarize_project_batch()` method (~80 lines)
  - Removed `project=` parameter from summary save calls
  - `project` column kept in DB for backward compatibility but not populated

### 2025-12-12 - Phase 9: Report Generation Cleanup
- **Removed project detection from reports.py**:
  - Removed `ProjectDetector` import and usage
  - Removed `separate_projects` parameter from `generate()` method
  - Removed `_generate_project_sections()` and `_generate_project_aware_executive_summary()` methods
  - Reports now synthesize from existing LLM summaries (which already contain interpreted activity context)
- **Added focus context to reports**:
  - Added `_build_focus_context()` helper to aggregate app/window usage from focus events
  - Report prompts now include app usage breakdown for additional context
  - Updated prompts with guidance: "Do NOT assume different apps/windows are related unless clearly same project"
- **Removed project detection from web/app.py**:
  - Removed `ProjectDetector` import
  - Removed project-based filtering in summary details endpoint
  - `api_get_summaries_by_project` endpoint still works but groups under 'unknown' (backward compatible)

## Future Improvements
- **Database normalization**: Unify `threshold_summaries` and `daily_summaries` into single `summaries` table with type field (threshold, hourly, daily, weekly, custom), plus separate `prompts` table for API request storage. Supports hierarchical relationships (daily→hourly→threshold).

## Known Issues (TODO Comments Added)
- **Multi-monitor support**: ✅ RESOLVED - Captures only active monitor, stores monitor metadata
- **Wayland compatibility**: Assumes X11, needs display server detection (xdotool + xrandr requirement)
- **Permission handling**: Missing checks for directory/file access
- **Configuration**: ✅ RESOLVED - config.py with YAML-based ConfigManager
- **Error resilience**: Daemon needs better error recovery

## Testing
Run tests with: `pytest tests/ --cov=tracker --cov-report=html`
Test categories: capture, storage, dhash, integration

