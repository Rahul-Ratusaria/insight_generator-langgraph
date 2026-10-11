import sqlite3
from pathlib import Path
from .models import PageResult

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
 job_id TEXT NOT NULL, page INTEGER NOT NULL, payload TEXT NOT NULL,
 PRIMARY KEY (job_id, page)
);
CREATE TABLE IF NOT EXISTS jobs (
 job_id TEXT PRIMARY KEY, file_name TEXT NOT NULL, provider TEXT NOT NULL,
 model TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

class Store:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.close()

    def register(self, job_id, name, provider, model):
        with self.conn:
            self.conn.execute("INSERT OR IGNORE INTO jobs(job_id,file_name,provider,model) VALUES(?,?,?,?)", (job_id, name, provider, model))

    def save(self, job_id: str, page: PageResult):
        with self.conn:
            self.conn.execute("INSERT OR REPLACE INTO pages(job_id,page,payload) VALUES(?,?,?)", (job_id, page.page, page.model_dump_json()))

    def get(self, job_id: str, page: int) -> PageResult | None:
        row = self.conn.execute("SELECT payload FROM pages WHERE job_id=? AND page=?", (job_id, page)).fetchone()
        return PageResult.model_validate_json(row[0]) if row else None

    def list_pages(self, job_id: str) -> list[PageResult]:
        return [PageResult.model_validate_json(r[0]) for r in self.conn.execute("SELECT payload FROM pages WHERE job_id=? ORDER BY page", (job_id,))]
