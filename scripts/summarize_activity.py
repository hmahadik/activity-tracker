#!/usr/bin/env python3
"""CLI tool for generating session-based activity summaries.

Usage:
    python summarize_activity.py                     # Summarize unsummarized sessions
    python summarize_activity.py --session 42        # Specific session
    python summarize_activity.py --date 2025-12-01   # All sessions for date
    python summarize_activity.py --force             # Re-summarize even if exists
    python summarize_activity.py --dry-run           # Show what would be processed
"""

import argparse
import signal
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from tracker.sessions import SessionManager
from tracker.storage import ActivityStorage
from tracker.vision import HybridSummarizer

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global shutdown_requested
    if shutdown_requested:
        print("\nForce quit.")
        sys.exit(1)
    print("\nShutdown requested. Finishing current task...")
    shutdown_requested = True


def process_session_ocr(
    storage: ActivityStorage,
    summarizer: HybridSummarizer,
    session_id: int,
    screenshots: list[dict],
    dry_run: bool = False,
) -> list[dict]:
    """
    Process OCR for unique window titles in a session.

    Args:
        storage: Storage instance for database access.
        summarizer: Summarizer instance for OCR extraction.
        session_id: The session ID.
        screenshots: List of screenshot dicts for the session.
        dry_run: If True, don't actually run OCR.

    Returns:
        List of dicts with {window_title, ocr_text}.
    """
    # Get unique window titles
    unique_titles = storage.get_unique_window_titles_for_session(session_id)

    if not unique_titles:
        return []

    ocr_results = []

    for title in unique_titles:
        # Check cache first
        cached = storage.get_cached_ocr(session_id, title)
        if cached is not None:
            ocr_results.append({"window_title": title, "ocr_text": cached})
            continue

        if dry_run:
            ocr_results.append({"window_title": title, "ocr_text": "[would run OCR]"})
            continue

        # Find a screenshot with this title
        matching_screenshot = None
        for s in screenshots:
            if s.get("window_title") == title:
                matching_screenshot = s
                break

        if not matching_screenshot:
            continue

        # Run OCR
        try:
            ocr_text = summarizer.extract_ocr(matching_screenshot["filepath"])
            # Cache the result
            storage.cache_ocr(session_id, title, ocr_text, matching_screenshot["id"])
            ocr_results.append({"window_title": title, "ocr_text": ocr_text})
        except Exception as e:
            print(f"    OCR failed for '{title}': {e}")

    return ocr_results


def process_session(
    storage: ActivityStorage,
    session_manager: SessionManager,
    summarizer: HybridSummarizer,
    session: dict,
    dry_run: bool = False,
) -> bool:
    """
    Process a single session and generate summary.

    Args:
        storage: Storage instance for database access.
        session_manager: Session manager instance.
        summarizer: Summarizer instance for LLM calls.
        session: Session dict with id, start_time, etc.
        dry_run: If True, don't actually generate or save.

    Returns:
        True if summary was generated, False if skipped.
    """
    session_id = session["id"]
    start_time = session["start_time"]
    end_time = session.get("end_time", "ongoing")
    duration_seconds = session.get("duration_seconds", 0)
    duration_minutes = duration_seconds / 60 if duration_seconds else 0

    # Get screenshots for session
    screenshots = storage.get_session_screenshots(session_id)

    if len(screenshots) < 2:
        print(f"  Session {session_id} ({start_time[:16]}) - Skipped (only {len(screenshots)} screenshot(s))")
        return False

    # Process OCR for unique window titles
    ocr_texts = process_session_ocr(storage, summarizer, session_id, screenshots, dry_run)

    if dry_run:
        print(
            f"  Session {session_id} ({start_time[:16]}, {duration_minutes:.0f}m) - "
            f"Would process {len(screenshots)} screenshots, {len(ocr_texts)} window titles"
        )
        return False

    # Get previous session summary for context
    recent_summaries = storage.get_recent_summaries(1)
    previous_summary = recent_summaries[0] if recent_summaries else None

    # Generate summary
    try:
        summary, inference_ms = summarizer.summarize_session(
            screenshots=screenshots,
            ocr_texts=ocr_texts,
            previous_summary=previous_summary,
        )

        # Save to database
        storage.save_session_summary(
            session_id=session_id,
            summary=summary,
            model=summarizer.model,
            inference_ms=inference_ms,
        )

        # Format time range for display
        start_dt = datetime.fromisoformat(start_time)
        time_range = start_dt.strftime("%H:%M")
        if end_time and end_time != "ongoing":
            end_dt = datetime.fromisoformat(end_time)
            time_range += f"-{end_dt.strftime('%H:%M')}"

        print(f"  Session {session_id} ({time_range}, {duration_minutes:.0f}m): {summary}")
        return True

    except Exception as e:
        print(f"  Session {session_id} ({start_time[:16]}) - Error: {e}")
        return False


def process_date_sessions(
    storage: ActivityStorage,
    session_manager: SessionManager,
    summarizer: HybridSummarizer,
    date: str,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[int, int]:
    """
    Process all sessions for a specific date.

    Args:
        storage: Storage instance for database access.
        session_manager: Session manager instance.
        summarizer: Summarizer instance for LLM calls.
        date: Date string in YYYY-MM-DD format.
        force: If True, re-summarize sessions that already have summaries.
        dry_run: If True, don't actually generate or save.

    Returns:
        Tuple of (processed_count, skipped_count).
    """
    global shutdown_requested

    print(f"\nProcessing sessions for {date}:")

    sessions = session_manager.get_sessions_for_date(date)

    if not sessions:
        print("  No sessions found.")
        return 0, 0

    # Filter to unsummarized sessions unless force is set
    if not force:
        sessions = [s for s in sessions if s.get("summary") is None]

    if not sessions:
        print("  All sessions already summarized.")
        return 0, 0

    processed = 0
    skipped = 0

    for session in sessions:
        if shutdown_requested:
            print(f"  Stopping after {processed} processed, {skipped} skipped.")
            break

        if process_session(storage, session_manager, summarizer, session, dry_run):
            processed += 1
        else:
            skipped += 1

    return processed, skipped


def main():
    """Main entry point for the CLI tool."""
    global shutdown_requested

    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    parser = argparse.ArgumentParser(
        description="Generate session-based activity summaries using vision LLM.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--session",
        type=int,
        metavar="ID",
        help="Process a specific session by ID.",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="Process all sessions for a specific date (YYYY-MM-DD).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-summarize sessions even if summaries exist.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be processed without running.",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gemma3:27b-it-qat",
        help="Ollama model to use (default: gemma3:27b-it-qat).",
    )
    parser.add_argument(
        "--ollama-host",
        type=str,
        default="http://localhost:11434",
        help="Ollama API URL (default: http://localhost:11434).",
    )

    args = parser.parse_args()

    # Initialize storage and managers
    storage = ActivityStorage()
    session_manager = SessionManager(storage)
    summarizer = HybridSummarizer(model=args.model, ollama_host=args.ollama_host)

    # Check availability
    if not args.dry_run:
        if not summarizer.is_available():
            print("Error: Summarizer is not available.")
            print("\nPlease ensure:")
            print("  1. Tesseract is installed: sudo apt install tesseract-ocr")
            print("  2. Ollama Docker container is running:")
            print("     docker run -d --gpus=all -v ollama:/root/.ollama -p 11434:11434 --name ollama ollama/ollama")
            print(f"  3. Model is available: docker exec ollama ollama pull {args.model}")
            print(f"\nOllama host: {args.ollama_host}")
            sys.exit(1)

    if args.dry_run:
        print("[DRY RUN - No changes will be made]")

    total_processed = 0
    total_skipped = 0

    if args.session:
        # Process specific session
        session = session_manager.get_session(args.session)
        if not session:
            print(f"Error: Session {args.session} not found.")
            sys.exit(1)

        if session.get("summary") and not args.force:
            print(f"Session {args.session} already has a summary. Use --force to re-summarize.")
            sys.exit(0)

        print(f"Processing session {args.session}:")
        if process_session(storage, session_manager, summarizer, session, args.dry_run):
            total_processed = 1
        else:
            total_skipped = 1

    elif args.date:
        # Process all sessions for a date
        total_processed, total_skipped = process_date_sessions(
            storage=storage,
            session_manager=session_manager,
            summarizer=summarizer,
            date=args.date,
            force=args.force,
            dry_run=args.dry_run,
        )

    else:
        # Process all unsummarized sessions
        print("Processing unsummarized sessions:")
        sessions = session_manager.get_unsummarized_sessions()

        if not sessions:
            print("  No unsummarized sessions found.")
        else:
            for session in sessions:
                if shutdown_requested:
                    break

                if process_session(storage, session_manager, summarizer, session, args.dry_run):
                    total_processed += 1
                else:
                    total_skipped += 1

    # Final summary
    print(f"\nDone! Processed: {total_processed}, Skipped: {total_skipped}")

    if shutdown_requested:
        print("(Interrupted - partial results saved)")
        sys.exit(130)


if __name__ == "__main__":
    main()
