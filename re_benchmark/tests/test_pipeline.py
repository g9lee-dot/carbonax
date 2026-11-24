"""API 호출 없이 전체 흐름을 점검하는 테스트. 수치는 모두 가상의 더미 값이다(실제 경쟁사 데이터 아님)."""

import csv
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from re_bm import db, extract, review, scenario, validate  # noqa: E402
from re_bm.units import standardize  # noqa: E402


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    db.init_db(c)
    c.execute("INSERT INTO reports(company_id, publication_year, file_path, sha256) VALUES ('intel',2026,'x','a')")
    c.execute("INSERT INTO reports(company_id, publication_year, file_path, sha256) VALUES ('micron',2026,'y','b')")
    return c


def add(conn, rid, co, y, geo, metric, v, unit, inst=None, status="approved"):
    conn.execute(
        "INSERT INTO re_metrics(report_id, company_id, data_year, geography, geography_level, metric, instrument,"
        " value_reported, unit_reported, value_std, data_quality, page, quote, quote_verified, review_status)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,'A_reported',1,'q',1,?)",
        (rid, co, y, geo, "global" if geo == "GLOBAL" else "country", metric, inst, v, unit,
         standardize(metric, v, unit), status))


def test_units():
    assert standardize("re_electricity", 2, "GWh") == 2000
    assert standardize("total_electricity", 3.6, "TJ") == pytest.approx(1000)
    assert standardize("re_ratio", 50, "%") == 50
    assert standardize("re_electricity", 1, "toe") is None  # 모르는 단위는 환산하지 않음


def test_page_selection_and_quote_check():
    pages = ["cover page", "Renewable electricity 1,200 MWh via PPA", "재생에너지 사용량 1,200 MWh, 녹색프리미엄"]
    assert extract.select_pages(pages) == [2, 3]
    assert extract.quote_on_page("1,200  MWh via PPA", pages, 2)
    assert not extract.quote_on_page("9,999 MWh", pages, 2)


def test_validate_and_derive(conn):
    add(conn, 1, "intel", 2025, "GLOBAL", "total_electricity", 100, "GWh")
    add(conn, 1, "intel", 2025, "GLOBAL", "re_electricity", 60, "GWh", "total")
    add(conn, 1, "intel", 2025, "GLOBAL", "re_electricity", 40, "GWh", "ppa_physical")
    add(conn, 1, "intel", 2025, "GLOBAL", "re_electricity", 10, "GWh", "unbundled_eac")  # 합계 50 != 60
    flags = validate.flags_for_metrics(conn)
    assert any("수단별 합계" in f for fs in flags.values() for f in fs)
    assert validate.derive_ratios(conn) == 1
    r = conn.execute("SELECT * FROM re_metrics WHERE metric='re_ratio'").fetchone()
    assert r["data_quality"] == "B_derived" and r["value_std"] == pytest.approx(60)


def test_pathway():
    p = scenario.pathway({2024: 20, 2025: 30}, {2030: 80}, [2025, 2026, 2030, 2035])
    assert p == {2025: 30, 2026: 40, 2030: 80, 2035: 80}


def test_scenario_country_fallback(conn, tmp_path):
    add(conn, 1, "intel", 2025, "GLOBAL", "re_ratio", 50, "%")
    add(conn, 2, "micron", 2025, "GLOBAL", "re_ratio", 30, "%")
    add(conn, 2, "micron", 2025, "US", "re_ratio", 70, "%")
    add(conn, 2, "micron", 2025, "US", "re_electricity", 7, "GWh", "ppa_physical")
    add(conn, 2, "micron", 2025, "US", "re_electricity", 3, "GWh", "unbundled_eac")
    add(conn, 1, "intel", 2025, "GLOBAL", "re_ratio", 99, "%", status="pending")  # 미승인은 무시돼야 함
    conn.execute("INSERT INTO re_targets(report_id, company_id, geography, target_year, target_re_ratio, review_status)"
                 " VALUES (1,'intel','GLOBAL',2030,100,'approved')")
    dem = tmp_path / "d.csv"
    dem.write_text("year,site,country,demand_mwh,grid_ef_tco2_per_mwh\n"
                   "2030,Austin,US,1000,0.4\n2030,KR_site,KR,1000,0.45\n")
    out = scenario.run(conn, dem, tmp_path / "o.csv", mode="country", method="average")
    rows = {r["site"]: r for r in csv.DictReader(out.open(encoding="utf-8-sig"))}
    assert rows["Austin"]["basis"] == "country_reported"
    assert float(rows["Austin"]["re_mwh_ppa_physical"]) == pytest.approx(490)  # 700 * 0.7
    assert rows["KR_site"]["basis"].startswith("fallback_global")
    # GLOBAL 2030: intel 100(목표), micron 30(유지) -> 평균 65
    assert float(rows["KR_site"]["bm_re_ratio_pct"]) == pytest.approx(65)
    assert float(rows["KR_site"]["scope2_mb_tco2e"]) == pytest.approx(350 * 0.45)


def test_review_roundtrip(conn, tmp_path):
    add(conn, 1, "intel", 2025, "GLOBAL", "re_ratio", 50, "%", status="pending")
    m, _ = review.export(conn, tmp_path)
    rows = list(csv.DictReader(m.open(encoding="utf-8-sig")))
    rows[0].update(review_status="approved", reviewer="tester", value_reported="51")
    with m.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    assert review.import_(conn, tmp_path) == 1
    assert conn.execute("SELECT value_std FROM re_metrics").fetchone()[0] == 51


def test_bm_path_country_and_fallback(conn):
    from re_bm import bm_path
    add(conn, 1, "intel", 2025, "GLOBAL", "re_ratio", 60, "%")
    add(conn, 2, "micron", 2025, "GLOBAL", "re_ratio", 20, "%")
    add(conn, 2, "micron", 2025, "US", "re_ratio", 100, "%")
    conn.execute("INSERT INTO re_targets(report_id, company_id, geography, target_year, target_re_ratio, review_status)"
                 " VALUES (1,'intel','GLOBAL',2030,100,'approved')")
    rows = bm_path.build(conn, [2025, 2030], ["GLOBAL", "US", "KR"], "average", None, "country")
    r = {(x["year"], x["geography"]): x for x in rows}
    assert r[(2030, "GLOBAL")]["bm_re_ratio_pct"] == 60          # (100 + 20) / 2
    assert r[(2030, "US")]["basis"] == "country_reported" and r[(2030, "US")]["bm_re_ratio_pct"] == 100
    assert r[(2030, "KR")]["basis"] == "fallback_global" and r[(2030, "KR")]["bm_re_ratio_pct"] == 60
    lead = bm_path.build(conn, [2030], ["KR"], "leader", None, "global")
    assert lead[0]["bm_re_ratio_pct"] == 100 and lead[0]["basis"] == "global"
    pkg = bm_path.package(conn, rows, [2025, 2030], ["GLOBAL", "US", "KR"], "average", None, "country")
    assert len(pkg["targets"]) == 6 and pkg["evidence"]["targets"][0]["re_ratio_pct"] == 100
