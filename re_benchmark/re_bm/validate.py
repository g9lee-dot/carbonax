"""적재 데이터 자동 점검 + 공시값으로부터 비율 산출(B_derived).

자동 점검은 사람 검토를 대체하지 않는다. 점검 결과는 검토 CSV 의 'flags' 열로 전달된다.
"""

from collections import defaultdict

TOL = 0.02  # 2% 허용 오차


def flags_for_metrics(conn) -> dict[int, list[str]]:
    flags: dict[int, list[str]] = defaultdict(list)
    rows = conn.execute("SELECT * FROM re_metrics WHERE review_status != 'rejected'").fetchall()

    for r in rows:
        if not r["quote_verified"]:
            flags[r["metric_id"]].append("인용문이 페이지에서 확인되지 않음")
        if r["value_std"] is None:
            flags[r["metric_id"]].append(f"단위 환산 불가({r['unit_reported']})")
        if r["metric"] == "re_ratio" and r["value_std"] is not None and not 0 <= r["value_std"] <= 100:
            flags[r["metric_id"]].append("비율이 0~100% 범위 밖")

    groups = defaultdict(list)
    for r in rows:
        groups[(r["report_id"], r["company_id"], r["data_year"], r["geography"])].append(r)

    for (_, _, year, geo), g in groups.items():
        get = lambda m, inst=None: [x for x in g if x["metric"] == m and (inst is None or x["instrument"] == inst)]
        total = get("total_electricity")
        re_total = get("re_electricity", "total")
        parts = [x for x in get("re_electricity") if x["instrument"] not in ("total", None)]
        ratio = get("re_ratio")

        # 수단별 합계 = RE 총량
        if re_total and parts and re_total[0]["value_std"] and all(p["value_std"] for p in parts):
            s = sum(p["value_std"] for p in parts)
            if abs(s - re_total[0]["value_std"]) > TOL * re_total[0]["value_std"]:
                for x in parts + re_total:
                    flags[x["metric_id"]].append(f"수단별 합계({s:,.0f}) != RE 총량({re_total[0]['value_std']:,.0f})")
        # 공시 비율 = RE 총량 / 총 전력
        if ratio and re_total and total and all(x[0]["value_std"] for x in (ratio, re_total, total)):
            calc = 100 * re_total[0]["value_std"] / total[0]["value_std"]
            if abs(calc - ratio[0]["value_std"]) > 1.0:  # 1%p
                flags[ratio[0]["metric_id"]].append(
                    f"공시 비율 {ratio[0]['value_std']:.1f}% vs 계산 {calc:.1f}% (경계·정의 차이 확인)")

    # 같은 지표의 연도 간 급변 (보고서가 달라도 비교)
    series = defaultdict(dict)
    for r in rows:
        if r["value_std"] is not None and r["metric"] in ("total_electricity", "re_ratio"):
            series[(r["company_id"], r["geography"], r["metric"])][r["data_year"]] = r
    for s in series.values():
        for y in sorted(s):
            if y - 1 in s and s[y - 1]["value_std"]:
                chg = s[y]["value_std"] / s[y - 1]["value_std"] - 1
                if abs(chg) > 0.5:
                    flags[s[y]["metric_id"]].append(f"전년 대비 {chg:+.0%} 변동")
    return flags


def derive_ratios(conn) -> int:
    """비율이 공시되지 않은 (기업, 연도, 지역)에 대해 RE 총량/총 전력으로 B_derived 비율을 만든다.
    원천 두 값이 모두 approved 일 때만 생성한다."""
    rows = conn.execute("""
        SELECT t.report_id, t.company_id, t.data_year, t.geography, t.geography_level,
               t.value_std AS total, r.value_std AS re, t.metric_id AS tid, r.metric_id AS rid, t.page AS tp, r.page AS rp
        FROM re_metrics t JOIN re_metrics r
          ON t.company_id=r.company_id AND t.data_year=r.data_year AND t.geography=r.geography AND t.report_id=r.report_id
        WHERE t.metric='total_electricity' AND r.metric='re_electricity' AND r.instrument='total'
          AND t.review_status='approved' AND r.review_status='approved'
          AND t.value_std > 0 AND r.value_std IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM re_metrics x WHERE x.company_id=t.company_id AND x.data_year=t.data_year
                          AND x.geography=t.geography AND x.metric='re_ratio' AND x.review_status!='rejected')
    """).fetchall()
    for r in rows:
        ratio = 100 * r["re"] / r["total"]
        conn.execute(
            "INSERT INTO re_metrics(report_id, company_id, data_year, geography, geography_level, metric, instrument,"
            " value_reported, unit_reported, value_std, data_quality, derivation_note, review_status, extracted_by)"
            " VALUES (?,?,?,?,?,'re_ratio',NULL,?,'%',?,'B_derived',?,'approved','derived')",
            (r["report_id"], r["company_id"], r["data_year"], r["geography"], r["geography_level"], ratio, ratio,
             f"RE 총량(metric_id {r['rid']}, p.{r['rp']}) / 총 전력(metric_id {r['tid']}, p.{r['tp']})"),
        )
    conn.commit()
    return len(rows)
