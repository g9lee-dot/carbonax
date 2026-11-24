"""경쟁사 BM 수준 비교 생성기: 우리 회사 수요 없이 경쟁사 공시값만으로 '누구 수준을 따라가면' 시나리오들을 만든다.

시나리오 (모두 전사 RE 전력 비율 기준)
- industry_max : 업계 최고 수준 (연도마다 포함 회사 경로 중 최고값, 그 연도의 선도 회사 기록)
- industry_avg : 업계 평균 수준
- industry_min : 업계 최저 수준 (연도마다 최저값, 그 연도의 최저 회사 기록)
- <company_id> : 해당 회사 수준 (예: tsmc, intel)

회사별 경로 규칙: 승인된 A/B 공시값만 사용, 최근 실적 -> 공시 목표연도까지 선형 보간, 마지막 목표 이후 유지,
목표가 없으면 최근 실적 유지. 지역(국가)별 값은 시나리오에 쓰지 않고 각주 정보(regional_notes)로만 제공한다.

출력
- CSV (wide): year, industry_max, industry_max_by, industry_avg, industry_min, industry_min_by, <company> ...
- JSON 시나리오 패키지: 시나리오별 경로 + 근거 + 지역 각주
"""

import csv
import json
import statistics
from datetime import date
from pathlib import Path

from .scenario import _actuals, _targets, pathway

INDUSTRY = [("industry_max", "업계 최고 수준"), ("industry_avg", "업계 평균 수준"), ("industry_min", "업계 최저 수준")]


def company_names(conn) -> dict[str, str]:
    return {r["company_id"]: r["name"] for r in conn.execute("SELECT company_id, name FROM companies ORDER BY company_id")}


def company_paths(conn, years: list[int], companies: list[str] | None = None) -> dict[str, dict[int, float | None]]:
    act, tgt = _actuals(conn, "GLOBAL"), _targets(conn, "GLOBAL")
    cos = [c for c in (companies or sorted(act)) if c in act]
    return {c: pathway(act[c], tgt.get(c, {}), years) for c in cos}


def build(conn, years: list[int], companies: list[str] | None = None) -> list[dict]:
    """연도별 한 줄: 업계 최고/평균/최저 + 회사별 수준."""
    paths = company_paths(conn, years, companies)
    rows = []
    for y in years:
        vals = {c: p[y] for c, p in paths.items() if p[y] is not None}
        row = {"year": y}
        if vals:
            hi, lo = max(vals.values()), min(vals.values())
            row.update(industry_max=round(hi, 2), industry_max_by=",".join(sorted(c for c, v in vals.items() if v == hi)),
                       industry_avg=round(statistics.fmean(vals.values()), 2),
                       industry_min=round(lo, 2), industry_min_by=",".join(sorted(c for c, v in vals.items() if v == lo)),
                       n_companies=len(vals))
        else:
            row.update(industry_max=None, industry_max_by="", industry_avg=None, industry_min=None, industry_min_by="",
                       n_companies=0)
        for c in paths:
            row[c] = None if paths[c][y] is None else round(paths[c][y], 2)
        rows.append(row)
    return rows


def regional_notes(conn, companies: list[str] | None = None) -> list[dict]:
    """각주용: 경쟁사가 국가·권역 단위로 공시한 RE 비율 (최신 연도). 시나리오 계산에는 쓰지 않는다."""
    q = "" if not companies else f" AND m.company_id IN ({','.join('?' * len(companies))})"
    rows = conn.execute(
        "SELECT m.geography, m.company_id, m.data_year, m.value_std, m.page, rp.title AS report"
        " FROM re_metrics m JOIN reports rp USING(report_id)"
        " WHERE m.metric='re_ratio' AND m.geography!='GLOBAL' AND m.review_status='approved'"
        " AND m.data_quality IN ('A_reported','B_derived')" + q +
        " ORDER BY m.geography, m.company_id, m.data_year DESC", companies or []).fetchall()
    seen, out = set(), []
    for r in rows:
        if (r["geography"], r["company_id"]) in seen:
            continue
        seen.add((r["geography"], r["company_id"]))
        out.append({"geography": r["geography"], "company_id": r["company_id"], "year": r["data_year"],
                    "re_ratio_pct": r["value_std"], "report": r["report"], "page": r["page"]})
    return out


def evidence(conn, companies: list[str] | None) -> dict:
    q = "" if not companies else f" AND company_id IN ({','.join('?' * len(companies))})"
    args = companies or []
    metrics = [dict(r) for r in conn.execute(
        "SELECT m.metric_id, m.company_id, m.data_year, m.value_std AS re_ratio_pct, m.data_quality,"
        " rp.title AS report, m.page, m.quote FROM re_metrics m JOIN reports rp USING(report_id)"
        " WHERE m.metric='re_ratio' AND m.geography='GLOBAL' AND m.review_status='approved'"
        " AND m.data_quality IN ('A_reported','B_derived')" + q.replace("company_id", "m.company_id") +
        " ORDER BY m.company_id, m.data_year", args)]
    targets = [dict(r) for r in conn.execute(
        "SELECT t.target_id, t.company_id, t.target_year, t.target_re_ratio AS re_ratio_pct,"
        " rp.title AS report, t.page, t.quote, t.scope_note FROM re_targets t JOIN reports rp USING(report_id)"
        " WHERE t.geography='GLOBAL' AND t.review_status='approved'" + q.replace("company_id", "t.company_id") +
        " ORDER BY t.company_id, t.target_year", args)]
    contracts = [dict(r) for r in conn.execute(
        "SELECT company_id, country, instrument, technology, capacity_mw, annual_mwh, start_year, counterparty, page"
        " FROM re_contracts WHERE review_status='approved'" + q + " ORDER BY company_id", args)]
    return {"actuals": metrics, "targets": targets, "reference_contracts": contracts}


def data_status(conn) -> str:
    assumed = conn.execute("SELECT COUNT(*) FROM re_metrics WHERE reviewer='bulk_assumed'").fetchone()[0]
    pending = conn.execute("SELECT COUNT(*) FROM re_metrics WHERE review_status='pending'").fetchone()[0]
    if assumed:
        return "approved (bulk assumed, not reviewed)"
    return "approved" if not pending else f"approved, {pending} pending excluded"


def package(conn, rows: list[dict], years: list[int], companies: list[str] | None = None) -> dict:
    names = company_names(conn)
    cos = [k for k in rows[0] if k in names]
    scen = [{"id": sid, "label": label,
             "path": [{"year": r["year"], "re_ratio_pct": r[sid],
                       **({"set_by": r[f"{sid}_by"]} if f"{sid}_by" in r else {})} for r in rows]}
            for sid, label in INDUSTRY]
    scen += [{"id": c, "label": f"{names[c]} 수준", "path": [{"year": r["year"], "re_ratio_pct": r[c]} for r in rows]}
             for c in cos]
    return {
        "package_id": "competitor_bm_levels",
        "source": "REBM",
        "generated_at": date.today().isoformat(),
        "basis": "company-wide (GLOBAL) renewable electricity share, %",
        "companies": cos,
        "years": [years[0], years[-1]],
        "data_status": data_status(conn),
        "rules": "approved A/B values only; each company: latest actual -> disclosed targets by linear interpolation, "
                 "then held flat (no target: latest actual held); industry_max/avg/min computed per year across companies",
        "scenarios": scen,
        "regional_notes": {
            "note": "Regional (country) disclosures are NOT applied to the scenarios; listed for reference only.",
            "disclosures": regional_notes(conn, companies),
        },
        "evidence": evidence(conn, companies),
    }


def write(rows: list[dict], pkg: dict, out_dir: Path, stem: str = "bm_levels") -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    c, j = out_dir / f"{stem}.csv", out_dir / f"{stem}.json"
    with c.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    j.write_text(json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    return c, j
