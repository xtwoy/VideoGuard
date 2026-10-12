"""One SQLite table is sufficient for the submission MVP."""
from __future__ import annotations
import json
from contextlib import closing
import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS reviews (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  video_name TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  duration_ms INTEGER NOT NULL,
  mode TEXT NOT NULL CHECK(mode IN ('LIVE','DEMO')),
  status TEXT NOT NULL CHECK(status IN ('DONE','ERROR')),
  result_json TEXT NOT NULL,
  error_text TEXT NOT NULL DEFAULT ''
);
"""

def database_path() -> Path:
    path=Path(os.getenv("VIDEOGUARD_DB", str(Path(__file__).parent/"data"/"reviews.db")))
    path.parent.mkdir(parents=True,exist_ok=True)
    return path

def connect():
    connection=sqlite3.connect(database_path(), timeout=5)
    connection.row_factory=sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(SCHEMA)
    return connection

def save_review(review: dict):
    with closing(connect()) as db:
        with db:
            db.execute(
                "INSERT INTO reviews (id,video_name,sha256,duration_ms,mode,status,result_json,error_text)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (review["id"],review["video_name"],review["sha256"],review["duration_ms"],
                 review["mode"],review["status"],
                 json.dumps(review["result"],ensure_ascii=False),review.get("error",""))
            )

def get_review(review_id: str):
    with closing(connect()) as db:
        row=db.execute(
            "SELECT * FROM reviews WHERE id=?", (review_id,)
        ).fetchone()
    if not row: return None
    return {
        "id":row["id"],"created_at":row["created_at"],
        "video_name":row["video_name"],"sha256":row["sha256"],
        "duration_ms":row["duration_ms"],"mode":row["mode"],
        "status":row["status"],"result":json.loads(row["result_json"]),
        "error":row["error_text"]
    }
