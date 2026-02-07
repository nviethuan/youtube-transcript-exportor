# Database module for transcript storage
from pathlib import Path

db_path = Path.home() / ".yt-transcript" / "database.db"
db_path.parent.mkdir(parents=True, exist_ok=True)
