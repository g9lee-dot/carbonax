"""경쟁사 벤치마크(BM) 시나리오.

경쟁사의 공시 RE 비율 실적과 목표로 연도별 경로를 만들고, 우리 회사 사업장별 전력수요에 적용한다.
- 승인(approved)된 A_reported / B_derived 값만 사용한다. C_estimated 는 사용하지 않는다.
- mode='global' : 경쟁사 전사(GLOBAL) 경로를 모든 사업장에 동일 적용 (가장 보수적이고 방어 가능한 기본값)
- mode='country': 사업장 국가에 대해 경쟁사가 '그 국가 값을 직접 공시한 경우'에만 국가 경로를 쓰고,
                  없으면 GLOBAL 경로로 대체한다. 대체 여부는 결과의 basis 열에 남긴다.
"""

import csv
import statistics
from collections import defaultdict
from pathlib import Path

INSTRUMENTS = ["onsite", "ppa_physical", "ppa_virtual", "green_tariff", "unbundled_eac", "other", "unspecified"]


def _actuals(conn, geography: str) -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = defaultdict(dict)
    for r in conn.execute(
        "SELECT company_id, data_year, value_std, data_quality FROM re_metrics WHERE metric='re_ratio'"
        " AND geography=? AND review_status='approved' AND data_quality IN ('A_reported','B_derived')"
        " AND value_std IS NOT NULL ORDER BY data_quality DESC",  # A 가 B 를 덮어쓰도록 B 먼저
        (geography,),
    ):
        out[r["company_id"]][r["data_year"]] = r["value_std"]
    return out


def _targets(conn, geography: str) -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = defaultdict(dict)
    for r in conn.execute(
        "SELECT company_id, target_year, target_re_ratio FROM re_targets WHERE geography=? AND review_status='approved'",
        (geography,),
    ):
        out[r["company_id"]][r["target_year"]] = r["target_re_ratio"]
    return out


def pathway(actual: dict[int, float], targets: dict[int, float], years: list[int]) -> dict[int, float | None]:
    """마지막 실적 -> 각 목표연도까지 선형 보간, 마지막 목표 이후는 유지. 실적 연도는 실적값."""
    if not actual:
        return {y: None for y in years}
    last_y = max(actual)
    pts = [(last_y, actual[last_y])] + sorted((y, v) for y, v in targets.items() if y > last_y)
    res = {}
    for y in years:
        if y in actual:
            res[y] = actual[y]
        elif y < last_y:
            res[y] = None
        else:
            for (y0, v0), (y1, v1) in zip(pts, pts[1:]):
                if y0 <= y <= y1:
                    res[y] = v0 + (v1 - v0) * (y - y0) / (y1 - y0)
                    break
            else:
                res[y] = pts[-1][1]
    return res


def _aggregate(vals: dict[str, float], method: str) -> float:
    if method == "leader":
        return max(vals.values())
    if method == "average":
        return statistics.fmean(vals.values())
    if method == "median":
        return statistics.median(vals.values())
    return vals[method]  # 특정 회사 company_id


def _instrument_mix(conn, geography: str, companies: list[str]) -> dict[str, float]:
    """해당 경쟁사들의 최신 승인 연도 수단별 RE 사용량 구성비(합산 기준)."""
    tot = defaultdict(float)
    for c in companies:
        row = conn.execute(
            "SELECT MAX(data_year) y FROM re_metrics WHERE company_id=? AND geography=? AND metric='re_electricity'"
            " AND instrument NOT IN ('total') AND review_status='approved' AND value_std IS NOT NULL", (c, geography),
        ).fetchone()
        if row["y"] is None:
            continue
        for r in conn.execute(
            "SELECT instrument, value_std FROM re_metrics WHERE company_id=? AND geography=? AND data_year=?"
            " AND metric='re_electricity' AND instrument NOT IN ('total') AND review_status='approved'"
            " AND value_std IS NOT NULL", (c, geography, row["y"]),
        ):
            tot[r["instrument"]] += r["value_std"]
    s = sum(tot.values())
    return {k: v / s for k, v in tot.items()} if s else {"unspecified": 1.0}


def benchmark_path(conn, geography: str, years: list[int], method: str, companies: list[str] | None):
    act, tgt = _actuals(conn, geography), _targets(conn, geography)
    cos = [c for c in (companies or act.keys()) if c in act]
    paths = {c: pathway(act[c], tgt.get(c, {}), years) for c in cos}
    out = {}
    for y in years:
        vals = {c: p[y] for c, p in paths.items() if p[y] is not None}
        if method not in ("leader", "average", "median") and method not in vals:
            out[y] = (None, [])
        else:
            out[y] = (_aggregate(vals, method), sorted(vals)) if vals else (None, [])
    return out, cos


def run(conn, demand_csv: Path, out_csv: Path, mode: str = "global", method: str = "average",
        companies: list[str] | None = None) -> Path:
    """demand_csv 열: year, site, country, demand_mwh[, grid_ef_tco2_per_mwh]"""
    with demand_csv.open(encoding="utf-8-sig") as f:
        demand = list(csv.DictReader(f))
    years = sorted({int(d["year"]) for d in demand})

    cache = {}

    def bm(geo):
        if geo not in cache:
            path, cos = benchmark_path(conn, geo, years, method, companies)
            cache[geo] = (path, _instrument_mix(conn, geo, cos) if cos else {"unspecified": 1.0})
        return cache[geo]

    rows = []
    for d in demand:
        y, country = int(d["year"]), d["country"].upper()
        geo_used, basis = "GLOBAL", "global"
        if mode == "country":
            path, _ = bm(country)
            if path[y][0] is not None:
                geo_used, basis = country, "country_reported"
            else:
                basis = "fallback_global(해당 국가 공시값 없음)"
        path, mix = bm(geo_used)
        ratio, used = path[y]
        dem = float(d["demand_mwh"])
        re_mwh = None if ratio is None else dem * ratio / 100
        row = {"year": y, "site": d["site"], "country": country, "demand_mwh": dem,
               "bm_re_ratio_pct": None if ratio is None else round(ratio, 2),
               "re_mwh": None if re_mwh is None else round(re_mwh, 1),
               "basis": basis, "bm_method": method, "bm_companies": ",".join(used)}
        for inst in INSTRUMENTS:
            row[f"re_mwh_{inst}"] = None if re_mwh is None else round(re_mwh * mix.get(inst, 0.0), 1)
        ef = d.get("grid_ef_tco2_per_mwh")
        row["scope2_mb_tco2e"] = (round((dem - re_mwh) * float(ef), 1) if ef and re_mwh is not None else None)
        rows.append(row)

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    return out_csv
