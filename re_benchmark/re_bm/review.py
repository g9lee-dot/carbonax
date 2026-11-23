"""사람 검토 루프: pending 항목을 CSV 로 내보내고, 검토 결과(approved/rejected, 수정값)를 다시 반영한다."""

import csv
from pathlib import Path

from .units import standardize
from .validate import flags_for_metrics

METRIC_COLS = ["metric_id", "company_id", "data_year", "geography", "geography_level", "metric", "instrument",
               "value_reported", "unit_reported", "value_std", "page", "quote", "quote_verified", "flags",
               "review_status", "reviewer", "review_note"]
TARGET_COLS = ["target_id", "company_id", "geography", "target_year", "target_re_ratio", "base_year", "initiative",
               "scope_note", "page", "quote", "quote_verified", "review_status", "reviewer", "review_note"]


def export(conn, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    flags = flags_for_metrics(conn)
    m_path, t_path = out_dir / "review_metrics.csv", out_dir / "review_targets.csv"
    with m_path.open("w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig: Excel 한글 깨짐 방지
        w = csv.DictWriter(f, METRIC_COLS)
        w.writeheader()
        for r in conn.execute("SELECT * FROM re_metrics WHERE review_status='pending' "
                              "ORDER BY company_id, data_year, geography, metric"):
            d = {k: r[k] for k in METRIC_COLS if k != "flags"}
            d["flags"] = "; ".join(flags.get(r["metric_id"], []))
            w.writerow(d)
    with t_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, TARGET_COLS)
        w.writeheader()
        for r in conn.execute("SELECT * FROM re_targets WHERE review_status='pending' ORDER BY company_id, target_year"):
            w.writerow({k: r[k] for k in TARGET_COLS})
    return m_path, t_path


def _read(path: Path):
    with path.open(encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def import_(conn, out_dir: Path) -> int:
    """검토자가 review_status / reviewer / review_note 를 채우고, 필요시 value_reported/unit_reported 를 수정한다."""
    n = 0
    m_path, t_path = out_dir / "review_metrics.csv", out_dir / "review_targets.csv"
    if m_path.exists():
        for row in _read(m_path):
            if row["review_status"] not in ("approved", "rejected"):
                continue
            if row["review_status"] == "approved" and not row["reviewer"]:
                raise ValueError(f"metric_id {row['metric_id']}: approved 에는 reviewer 가 필요합니다")
            v, u = float(row["value_reported"]), row["unit_reported"]
            conn.execute(
                "UPDATE re_metrics SET review_status=?, reviewer=?, review_note=?, value_reported=?, unit_reported=?,"
                " value_std=? WHERE metric_id=?",
                (row["review_status"], row["reviewer"], row["review_note"], v, u,
                 standardize(row["metric"], v, u), int(row["metric_id"])),
            )
            n += 1
    if t_path.exists():
        for row in _read(t_path):
            if row["review_status"] not in ("approved", "rejected"):
                continue
            if row["review_status"] == "approved" and not row["reviewer"]:
                raise ValueError(f"target_id {row['target_id']}: approved 에는 reviewer 가 필요합니다")
            conn.execute(
                "UPDATE re_targets SET review_status=?, reviewer=?, review_note=?, target_year=?, target_re_ratio=?"
                " WHERE target_id=?",
                (row["review_status"], row["reviewer"], row["review_note"], int(row["target_year"]),
                 float(row["target_re_ratio"]), int(row["target_id"])),
            )
            n += 1
    conn.commit()
    return n
