import sqlite3

from youtubetranscriptexportor.db import db_path


class TranscriptService:
    def __init__(self):
        self.db_path = str(db_path)
        self._create_table()

    def _get_connection(self):
        # Kết nối SQLite (check_same_thread=False cần thiết cho ứng dụng Flet đa luồng)
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _create_table(self):
        with self._get_connection() as conn:
            conn.execute("""
        CREATE TABLE IF NOT EXISTS transcripts (
          video_id TEXT PRIMARY KEY,
          transcript TEXT NOT NULL
        )
      """)

    def upsert(self, video_id, transcript):
        sql = """
      INSERT INTO transcripts (video_id, transcript)
      VALUES (?, ?)
      ON CONFLICT(video_id) DO UPDATE SET
        transcript = excluded.transcript
    """
        try:
            with self._get_connection() as conn:
                conn.execute(sql, (video_id, transcript))
            return True
        except sqlite3.Error as e:
            print(f"Lỗi database: {e}")
            return False

    def add_transcript(self, video_id, transcript):
        with self._get_connection() as conn:
            conn.execute(
                "INSERT INTO transcripts (video_id, transcript) VALUES (?, ?)",
                (video_id, transcript),
            )

    def get_transcript(self, video_id):
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT transcript FROM transcripts WHERE video_id = ?", (video_id,)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def update_transcript(self, video_id, new_transcript):
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE transcripts SET transcript = ? WHERE video_id = ?",
                (new_transcript, video_id),
            )

    def delete_transcript(self, video_id):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM transcripts WHERE video_id = ?", (video_id,))
