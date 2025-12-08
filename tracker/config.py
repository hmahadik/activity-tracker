"""Configuration settings for Activity Tracker.

This module contains configurable settings for the activity tracker,
including summarization model preferences and capture settings.
"""

# Ollama Docker settings
OLLAMA_HOST = "http://localhost:11434"
"""Base URL for Ollama API.

Default assumes Ollama Docker container running with:
  docker run -d --gpus=all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama

For remote Ollama servers, set to the appropriate URL (e.g., http://gpu-server:11434).
"""

# Summarizer settings
SUMMARIZER_MODEL = "gemma3:27b-it-qat"
"""Ollama model to use for vision summarization.

Recommended models:
- gemma3:27b-it-qat: Best quality, requires ~18GB VRAM
- gemma3:12b-it-qat: Good quality, requires ~8GB VRAM
- gemma3:4b-it-qat: Acceptable quality, requires ~3GB VRAM
"""

SUMMARIZER_SAMPLES_PER_HOUR = 5
"""Number of screenshots to sample per hour for summarization.

More samples provide better context but increase inference time.
Recommended range: 4-6 screenshots.
"""

OCR_ENABLED = True
"""Whether to use Tesseract OCR for text extraction.

When enabled, OCR text from a middle screenshot is included
in the summarization prompt to ground the LLM's analysis.
Requires tesseract-ocr to be installed.
"""

# Capture settings
CAPTURE_INTERVAL_SECONDS = 30
"""Interval between screenshot captures in seconds."""

DUPLICATE_THRESHOLD = 3
"""Hamming distance threshold for duplicate detection.

Screenshots with a perceptual hash distance less than this
value are considered duplicates and skipped.
"""

# Data paths
DATA_DIR_NAME = "activity-tracker-data"
"""Name of the data directory in user's home folder."""

SCREENSHOTS_SUBDIR = "screenshots"
"""Subdirectory for screenshot storage."""

DATABASE_NAME = "activity.db"
"""SQLite database filename."""
