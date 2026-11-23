import sqlite3
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "re_benchmark.db"


def connect(path: Path | str = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript((ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))
    cfg = yaml.safe_load((ROOT / "config" / "competitors.yaml").read_text(encoding="utf-8"))
    for c in cfg["companies"]:
        conn.execute(
            "INSERT INTO companies(company_id, name, hq_country) VALUES (?,?,?) "
            "ON CONFLICT(company_id) DO UPDATE SET name=excluded.name, hq_country=excluded.hq_country",
            (c["company_id"], c["name"], c.get("hq_country")),
        )
    conn.commit()
