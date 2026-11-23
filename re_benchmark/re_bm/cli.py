import argparse
from pathlib import Path

from . import db, extract, review, scenario, validate


def main():
    p = argparse.ArgumentParser(prog="re_bm", description="경쟁사 RE 벤치마크 DB / 시나리오")
    p.add_argument("--db", default=str(db.DEFAULT_DB))
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="DB 생성 및 경쟁사 목록 반영")

    e = sub.add_parser("extract", help="보고서 PDF 추출 -> pending 적재")
    e.add_argument("company_id")
    e.add_argument("pdf", type=Path)
    e.add_argument("--year", type=int, required=True, help="보고서 발간연도")
    e.add_argument("--from-json", type=Path, help="API 대신 Extraction 스키마 JSON 파일로 적재")

    r = sub.add_parser("review", help="검토 CSV 내보내기/반영")
    r.add_argument("action", choices=["export", "import"])
    r.add_argument("--dir", type=Path, default=db.ROOT / "data" / "review")

    sub.add_parser("derive", help="승인된 총량으로 RE 비율 산출(B_derived)")

    s = sub.add_parser("scenario", help="경쟁사 BM 시나리오 계산")
    s.add_argument("demand_csv", type=Path)
    s.add_argument("--out", type=Path, default=db.ROOT / "data" / "output" / "bm_scenario.csv")
    s.add_argument("--mode", choices=["global", "country"], default="global")
    s.add_argument("--method", default="average", help="leader | average | median | <company_id>")
    s.add_argument("--companies", help="쉼표 구분 company_id (기본: 데이터 있는 전체)")

    a = p.parse_args()
    conn = db.connect(a.db)
    if a.cmd == "init":
        db.init_db(conn)
        print(f"initialized {a.db}")
    elif a.cmd == "extract":
        rid = extract.load_report(conn, a.company_id, a.pdf, a.year, json_path=a.from_json)
        n = conn.execute("SELECT COUNT(*) FROM re_metrics WHERE report_id=?", (rid,)).fetchone()[0]
        print(f"report_id={rid}: {n} metrics loaded as pending. Next: review export")
    elif a.cmd == "review":
        if a.action == "export":
            print("written:", *review.export(conn, a.dir))
        else:
            print(f"{review.import_(conn, a.dir)} rows updated")
    elif a.cmd == "derive":
        print(f"{validate.derive_ratios(conn)} derived ratios added")
    elif a.cmd == "scenario":
        cos = a.companies.split(",") if a.companies else None
        print("written:", scenario.run(conn, a.demand_csv, a.out, a.mode, a.method, cos))


if __name__ == "__main__":
    main()
