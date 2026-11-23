"""승인된 벤치마크 데이터 + 더미 수요로 대화형 시나리오 계산 툴(HTML)을 만든다.

python -m re_bm.tool [--out tool/re_bm_tool.html]   (더미 수요 CSV 도 data/our_demand_dummy.csv 로 함께 생성)
계산 로직은 scenario.py 와 동일하게 JS 로 구현되어 있다 (경로 = 최근 실적 -> 목표 선형보간, 이후 유지).
"""

import argparse
import csv
import json
from pathlib import Path

from . import db

TEMPLATE = Path(__file__).with_name("tool_template.html")


def bm_data(conn) -> dict:
    out = {"companies": {}, "actual": {}, "targets": {}, "evidence": [], "reports": {}}
    for r in conn.execute("SELECT company_id, name FROM companies"):
        out["companies"][r["company_id"]] = r["name"]
    for r in conn.execute(
        "SELECT m.company_id, m.geography, m.data_year, m.value_std, m.page, m.quote, m.data_quality, rp.title"
        " FROM re_metrics m JOIN reports rp USING(report_id)"
        " WHERE m.metric='re_ratio' AND m.review_status='approved' AND m.data_quality IN ('A_reported','B_derived')"
        " AND m.value_std IS NOT NULL ORDER BY m.data_quality DESC"
    ):
        out["actual"].setdefault(r["geography"], {}).setdefault(r["company_id"], {})[str(r["data_year"])] = r["value_std"]
        out["evidence"].append({"co": r["company_id"], "geo": r["geography"], "kind": "실적", "year": r["data_year"],
                                "value": r["value_std"], "page": r["page"], "quote": r["quote"], "report": r["title"],
                                "quality": r["data_quality"]})
    for r in conn.execute(
        "SELECT t.company_id, t.geography, t.target_year, t.target_re_ratio, t.page, t.quote, t.scope_note, rp.title"
        " FROM re_targets t JOIN reports rp USING(report_id) WHERE t.review_status='approved'"
    ):
        out["targets"].setdefault(r["geography"], {}).setdefault(r["company_id"], {})[str(r["target_year"])] = r["target_re_ratio"]
        out["evidence"].append({"co": r["company_id"], "geo": r["geography"], "kind": "목표", "year": r["target_year"],
                                "value": r["target_re_ratio"], "page": r["page"], "quote": r["quote"], "report": r["title"],
                                "note": r["scope_note"]})
    for r in conn.execute("SELECT company_id, title, boundary_note FROM reports"):
        out["reports"].setdefault(r["company_id"], []).append({"title": r["title"], "note": r["boundary_note"]})
    out["evidence"].sort(key=lambda e: (e["co"], e["geo"] != "GLOBAL", e["geo"], e["kind"], e["year"]))
    return out


# 더미 사업장 전력수요 가정 (실제 회사 데이터 아님). 툴 화면에서 수정 가능.
# start: 가동 연도, demand: 가동 연도 수요(MWh), growth: 연 증가율(%), cap: 수요 상한(MWh, 0=없음), ef: 전력 배출계수(tCO2/MWh)
DUMMY_SITES = [
    {"site": "KR_Fab", "country": "KR", "start": 2026, "demand": 20_000_000, "growth": 3.0, "cap": 0, "ef": 0.4567},
    {"site": "CN_Xian", "country": "CN", "start": 2026, "demand": 3_000_000, "growth": 2.0, "cap": 0, "ef": 0.5703},
    {"site": "CN_Suzhou", "country": "CN", "start": 2026, "demand": 1_000_000, "growth": 1.0, "cap": 0, "ef": 0.5703},
    {"site": "US_Austin", "country": "US", "start": 2026, "demand": 2_500_000, "growth": 1.0, "cap": 0, "ef": 0.3700},
    {"site": "US_Taylor", "country": "US", "start": 2027, "demand": 500_000, "growth": 50.0, "cap": 6_000_000, "ef": 0.3700},
]
YEARS = list(range(2026, 2041))


def site_demand(s: dict, y: int) -> float:
    if y < s["start"]:
        return 0.0
    d = s["demand"] * (1 + s["growth"] / 100) ** (y - s["start"])
    return min(d, s["cap"]) if s["cap"] else d


def write_dummy_csv(path: Path) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["year", "site", "country", "demand_mwh", "grid_ef_tco2_per_mwh"])
        for y in YEARS:
            for s in DUMMY_SITES:
                w.writerow([y, s["site"], s["country"], round(site_demand(s, y)), s["ef"]])
    return path


def build(conn, out: Path) -> Path:
    payload = {"bm": bm_data(conn), "sites": DUMMY_SITES, "years": YEARS}
    html = TEMPLATE.read_text(encoding="utf-8").replace(
        "/*__DATA__*/null", json.dumps(payload, ensure_ascii=False).replace("</", "<\\/"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=str(db.DEFAULT_DB))
    p.add_argument("--out", type=Path, default=db.ROOT / "tool" / "re_bm_tool.html")
    a = p.parse_args()
    print("written:", write_dummy_csv(db.ROOT / "data" / "our_demand_dummy.csv"))
    print("written:", build(db.connect(a.db), a.out))


if __name__ == "__main__":
    main()
