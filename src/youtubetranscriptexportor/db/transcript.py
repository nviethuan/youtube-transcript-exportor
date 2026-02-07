import sqlite3
from pathlib import Path


class TranscriptService:
    """Service for managing YouTube transcript storage using SQLite."""

    def __init__(self, db_path=None):
        """Initialize the transcript service with a database path."""
        if db_path is None:
            # Use a default path in the user's home directory
            db_dir = Path.home() / ".yt_transcript"
            db_dir.mkdir(exist_ok=True)
            db_path = db_dir / "database.db"

        self.db_path = str(db_path)
        self._init_db()

    def _init_db(self):
        """Initialize the database with the transcripts table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
      CREATE TABLE IF NOT EXISTS transcripts (
        video_id TEXT PRIMARY KEY,
        transcript TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    """)

        conn.commit()
        conn.close()

    def get_transcript(self, video_id):
        """Retrieve a transcript by video ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT transcript FROM transcripts WHERE video_id = ?", (video_id,)
        )

        result = cursor.fetchone()
        conn.close()

        return result[0] if result else None

    def upsert(self, video_id, transcript):
        """Insert or update a transcript."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
      INSERT INTO transcripts (video_id, transcript, updated_at)
      VALUES (?, ?, CURRENT_TIMESTAMP)
      ON CONFLICT(video_id) 
      DO UPDATE SET 
          transcript = excluded.transcript,
          updated_at = CURRENT_TIMESTAMP
    """,
            (video_id, transcript),
        )

        conn.commit()
        conn.close()

    def delete(self, video_id):
        """Delete a transcript by video ID."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM transcripts WHERE video_id = ?", (video_id,))

        conn.commit()
        conn.close()

    def list_all(self):
        """List all stored transcripts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT video_id, created_at, updated_at FROM transcripts")

        results = cursor.fetchall()
        conn.close()

        return results
