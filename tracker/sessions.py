"""
Session management for activity tracking.

A session represents a continuous period of user activity, bounded by AFK gaps.
Sessions are created when the user becomes active and ended when they go AFK.
"""

import logging
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class SessionState(Enum):
    """Represents the current state of user activity."""
    ACTIVE = "active"
    AFK = "afk"


class SessionManager:
    """
    Manages activity sessions based on AFK detection.

    Coordinates with storage to create, update, and query sessions.
    Provides methods to link screenshots to sessions and track
    unique window titles for OCR optimization.

    Attributes:
        storage: StorageManager instance for database access.
        min_session_minutes: Minimum duration for a valid session.
    """

    def __init__(self, storage, min_session_minutes: int = 5):
        """
        Initialize the SessionManager.

        Args:
            storage: StorageManager instance for DB access.
            min_session_minutes: Ignore sessions shorter than this (default 5).
        """
        self.storage = storage
        self.min_session_minutes = min_session_minutes
        self._current_session_id: Optional[int] = None
        self._session_window_titles: set = set()

    def start_session(self) -> int:
        """
        Create a new session record.

        Returns:
            Session ID of the newly created session.
        """
        start_time = datetime.now()
        session_id = self.storage.create_session(start_time)
        self._current_session_id = session_id
        self._session_window_titles = set()

        logger.info(f"Started session {session_id} at {start_time.strftime('%H:%M:%S')}")
        return session_id

    def end_session(self, session_id: int) -> Optional[dict]:
        """
        End a session and calculate its duration.

        If the session is shorter than min_session_minutes, it will be
        deleted and None will be returned.

        Args:
            session_id: ID of the session to end.

        Returns:
            Session dict if valid (long enough), None if deleted.
        """
        end_time = datetime.now()
        session = self.storage.get_session(session_id)

        if not session:
            logger.warning(f"Session {session_id} not found")
            return None

        start_time = datetime.fromisoformat(session['start_time'])
        duration_seconds = int((end_time - start_time).total_seconds())
        duration_minutes = duration_seconds / 60

        if duration_minutes < self.min_session_minutes:
            logger.info(
                f"Session {session_id} too short ({duration_minutes:.1f}m < {self.min_session_minutes}m), deleting"
            )
            self.storage.delete_session(session_id)
            self._current_session_id = None
            self._session_window_titles = set()
            return None

        # Update session with end time and duration
        self.storage.end_session(session_id, end_time, duration_seconds)

        # Get updated session
        session = self.storage.get_session(session_id)
        logger.info(
            f"Ended session {session_id}: {duration_minutes:.1f}m, "
            f"{session.get('screenshot_count', 0)} screenshots, "
            f"{session.get('unique_windows', 0)} unique windows"
        )

        self._current_session_id = None
        self._session_window_titles = set()

        return session

    def get_current_session(self) -> Optional[dict]:
        """
        Get the currently active session.

        Returns:
            Session dict if there's an active session, None otherwise.
        """
        return self.storage.get_active_session()

    def get_current_session_id(self) -> Optional[int]:
        """
        Get the ID of the currently active session.

        Returns:
            Session ID or None if no active session.
        """
        return self._current_session_id

    def get_session(self, session_id: int) -> Optional[dict]:
        """
        Get a session by ID.

        Args:
            session_id: The session ID to retrieve.

        Returns:
            Session dict with all metadata, or None if not found.
        """
        return self.storage.get_session(session_id)

    def get_sessions_for_date(self, date: str) -> list[dict]:
        """
        Get all sessions for a specific date.

        Args:
            date: Date string in YYYY-MM-DD format.

        Returns:
            List of session dicts ordered by start_time.
        """
        return self.storage.get_sessions_for_date(date)

    def get_unsummarized_sessions(self) -> list[dict]:
        """
        Get sessions that have screenshots but no summary.

        Returns:
            List of session dicts that need summarization.
        """
        return self.storage.get_unsummarized_sessions()

    def get_recent_summaries(self, n: int = 3) -> list[str]:
        """
        Get the last N session summaries for context continuity.

        Args:
            n: Number of recent summaries to retrieve.

        Returns:
            List of summary strings, most recent first.
        """
        return self.storage.get_recent_summaries(n)

    def add_screenshot_to_session(self, session_id: int, screenshot_id: int):
        """
        Link a screenshot to a session.

        Args:
            session_id: The session to link to.
            screenshot_id: The screenshot to link.
        """
        self.storage.link_screenshot_to_session(session_id, screenshot_id)

    def track_window_title(self, session_id: int, window_title: str) -> bool:
        """
        Track a window title for the current session.

        Returns True if this is a new window title for the session
        (indicating OCR should be performed).

        Args:
            session_id: Current session ID.
            window_title: The window title to track.

        Returns:
            True if this is a new title for the session, False if seen before.
        """
        if not window_title:
            return False

        if window_title in self._session_window_titles:
            return False

        self._session_window_titles.add(window_title)
        return True

    def get_session_screenshots(self, session_id: int) -> list[dict]:
        """
        Get all screenshots for a session.

        Args:
            session_id: The session ID.

        Returns:
            List of screenshot dicts.
        """
        return self.storage.get_session_screenshots(session_id)

    def get_unique_window_titles(self, session_id: int) -> list[str]:
        """
        Get unique window titles for a session.

        Args:
            session_id: The session ID.

        Returns:
            List of unique window title strings.
        """
        return self.storage.get_unique_window_titles_for_session(session_id)

    def resume_active_session(self) -> Optional[int]:
        """
        Check for and resume any active session from the database.

        This is useful when the daemon restarts and there was an
        active session that wasn't properly closed.

        Returns:
            Session ID if an active session was found, None otherwise.
        """
        active_session = self.storage.get_active_session()
        if active_session:
            self._current_session_id = active_session['id']
            # Rebuild window titles set from existing screenshots
            titles = self.storage.get_unique_window_titles_for_session(active_session['id'])
            self._session_window_titles = set(titles)
            logger.info(f"Resumed active session {self._current_session_id}")
            return self._current_session_id
        return None
