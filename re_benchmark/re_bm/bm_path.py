"""경쟁사 BM 경로 생성기: 우리 회사 수요 없이 경쟁사 공시값만으로 연도·지역별 벤치마크 RE 비율을 만든다.

출력
- CSV (long): year, geography, bm_re_ratio_pct, basis, geo_used, bm_companies, <company>_pct ...
- JSON 시나리오 패키지: RE 시뮬레이터 등 다른 도구가 읽는 형식 (evidence 포함)

규칙은 scenario.py 와 동일하다 (승인된 A/B 값만, 실적 -> 목표 선형 보간 후 유지,
국가는 경쟁사가 그 국가를 공시했을 때만 국가 경로, 없으면 GLOBAL 로 대체).
"""

import csv
import json
from datetime import date
from pathlib import Path

from .scenario import _actuals, _aggregate, _targets, pathway

METHODS = ("average", "median", "leader")


def company_paths(conn, geography: str, years: list[int], companies: list[str] | None) -> dict[str, dict]:
    act, tgt = _actuals(conn, geography), _targets(conn, geography)
    cos = [c for c in (companies or sorted(act)) if c in act]
    return {c: pathway(act[c], tgt.get(c, {}), years) for c in cos}


def build(conn, years: list[int], geographies: list[str], method: str = "average",
          companies: list[str] | None = None, mode: str = "country") -> list[dict]:
    all_cos = companies or [r["company_id"] for r in conn.execute("SELECT company_id FROM companies ORDER BY company_id")]
    glob = company_paths(conn, "GLOBAL", years, all_cos)
    rows = []
    for geo in geographies:
        geo = geo.upper()
        own = company_paths(conn, geo, years, all_cos) if geo != "GLOBAL" else glob
        for y in years:
            if geo == "GLOBAL":
                paths, basis, used_geo = glob, "global", "GLOBAL"
            elif mode == "country" and any(p[y] is not None for p in own.values()):
                paths, basis, used_geo = own, "country_reported", geo
            else:
                paths, basis, used_geo = glob, ("global" if mode == "global" else "fallback_global"), "GLOBAL"
            vals = {c: p[y] for c, p in paths.items() if p[y] is not None}
            ok = vals and (method in METHODS or method in vals)
            row = {"year": y, "geography": geo, "bm_re_ratio_pct": round(_aggregate(vals, method), 2) if ok else None,
                   "basis": basis, "geo_used": used_geo, "bm_method": method, "bm_companies": ",".join(sorted(vals))}
            for c in all_cos:
                v = paths.get(c, {}).get(y)
                row[f"{c}_pct"] = None if v is None else round(v, 2)
            rows.append(row)
    return rows


def evidence(conn, companies: list[str] | None) -> dict:
    q = "" if not companies else f" AND company_id IN ({','.join('?' * len(companies))})"
    args = companies or []
    metrics = [dict(r) for r in conn.execute(
        "SELECT m.metric_id, m.company_id, m.geography, m.data_year, m.value_std AS re_ratio_pct, m.data_quality,"
        " rp.title AS report, m.page, m.quote FROM re_metrics m JOIN reports rp USING(report_id)"
        " WHERE m.metric='re_ratio' AND m.review_status='approved' AND m.data_quality IN ('A_reported','B_derived')" +
        q.replace("company_id", "m.company_id") + " ORDER BY m.company_id, m.geography, m.data_year", args)]
    targets = [dict(r) for r in conn.execute(
        "SELECT t.target_id, t.company_id, t.geography, t.target_year, t.target_re_ratio AS re_ratio_pct,"
        " rp.title AS report, t.page, t.quote, t.scope_note FROM re_targets t JOIN reports rp USING(report_id)"
        " WHERE t.review_status='approved'" + q.replace("company_id", "t.company_id") +
        " ORDER BY t.company_id, t.target_year", args)]
    contracts = [dict(r) for r in conn.execute(
        "SELECT company_id, country, instrument, technology, capacity_mw, annual_mwh, start_year, counterparty, page"
        " FROM re_contracts WHERE review_status='approved'" + q + " ORDER BY company_id", args)]
    return {"actuals": metrics, "targets": targets, "reference_contracts": contracts}


def package(conn, rows: list[dict], years, geographies, method, companies, mode) -> dict:
    pending = conn.execute("SELECT COUNT(*) FROM re_metrics WHERE review_status='pending'").fetchone()[0]
    assumed = conn.execute("SELECT COUNT(*) FROM re_metrics WHERE reviewer='bulk_assumed'").fetchone()[0]
    return {
        "scenario_id": f"competitor_bm_{method}_{mode}",
        "source": "REBM",
        "generated_at": date.today().isoformat(),
        "method": method, "mode": mode,
        "companies": companies or sorted({c for r in rows for c in r["bm_companies"].split(",") if c}),
        "years": [years[0], years[-1]], "geographies": geographies,
        "data_status": "approved (bulk assumed, not reviewed)" if assumed else
                       ("approved" if not pending else f"approved, {pending} pending excluded"),
        "rules": "approved A/B values only; actual -> disclosed target linear interpolation, then held flat; "
                 "country path only where a competitor disclosed that country, else GLOBAL (basis=fallback_global)",
        "targets": [{k: r[k] for k in ("year", "geography", "bm_re_ratio_pct", "basis", "bm_companies")} for r in rows],
        "evidence": evidence(conn, companies),
    }


def write(rows: list[dict], pkg: dict, out_dir: Path, stem: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    c, j = out_dir / f"{stem}.csv", out_dir / f"{stem}.json"
    with c.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    j.write_text(json.dumps(pkg, ensure_ascii=False, indent=1), encoding="utf-8")
    return c, j
