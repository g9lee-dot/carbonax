"""지속가능경영보고서 PDF -> RE 관련 페이지 선별 -> Claude 구조화 추출 -> DB 적재(pending)."""

import hashlib
import re
from pathlib import Path
from typing import Literal, Optional

import anthropic
import pdfplumber
from pydantic import BaseModel, Field

from .units import standardize

MODEL = "claude-opus-5-5"

# 페이지 선별 키워드 (영/한). 표가 많은 ESG 데이터 부록을 놓치지 않도록 넓게 잡는다.
KEYWORDS = [
    r"renewable", r"\bRE100\b", r"\bPPA\b", r"power purchase", r"\bREC\b", r"\bI-?REC", r"guarantee[s]? of origin",
    r"green tariff", r"green power", r"electricity consumption", r"purchased electricity", r"scope 2",
    r"market[- ]based", r"\bGRI 302", r"\bMWh\b", r"\bGWh\b",
    r"재생에너지", r"녹색프리미엄", r"전력\s*사용량", r"전력\s*구매", r"자가발전", r"인증서", r"시장\s*기반",
]
_KW = re.compile("|".join(KEYWORDS), re.IGNORECASE)
MIN_HITS = 2  # 키워드 2회 이상 등장한 페이지만 LLM 에 보낸다


# ---------- 추출 스키마 ----------
Instrument = Literal["total", "onsite", "ppa_physical", "ppa_virtual", "green_tariff", "unbundled_eac", "other", "unspecified"]
GeoLevel = Literal["global", "region", "country", "site"]


class Metric(BaseModel):
    data_year: int
    geography: str = Field(description="'GLOBAL' for company-wide; ISO-3166 alpha-2 country code; or site name")
    geography_level: GeoLevel
    metric: Literal["total_electricity", "re_electricity", "re_ratio", "scope2_market_based", "scope2_location_based"]
    instrument: Optional[Instrument] = Field(description="Only for re_electricity; else null")
    value: float = Field(description="Number exactly as printed in the report (no conversion)")
    unit: str = Field(description="Unit exactly as printed, e.g. MWh, GWh, %, tCO2e")
    page: int = Field(description="PDF page number where the value appears (the [PAGE n] marker)")
    quote: str = Field(description="Short verbatim excerpt from that page containing the value, copied exactly")


class Target(BaseModel):
    geography: str
    target_year: int
    target_re_ratio: float = Field(description="Target renewable electricity share in %")
    base_year: Optional[int]
    initiative: Optional[str] = Field(description="e.g. RE100, or null")
    scope_note: Optional[str] = Field(description="Conditions/boundary stated for the target")
    page: int
    quote: str


class Contract(BaseModel):
    country: Optional[str]
    instrument: Optional[Instrument]
    technology: Optional[str]
    capacity_mw: Optional[float]
    annual_mwh: Optional[float]
    term_years: Optional[float]
    start_year: Optional[int]
    counterparty: Optional[str]
    page: int
    quote: str


class Extraction(BaseModel):
    assurance: Optional[str] = Field(description="Third-party assurance of energy/GHG data as stated, or null")
    boundary_note: Optional[str] = Field(description="Reporting boundary for energy data as stated, or null")
    metrics: list[Metric]
    targets: list[Target]
    contracts: list[Contract]


SYSTEM = """You extract renewable-electricity data from a company's sustainability report for a benchmark database.

Rules:
- Extract only values explicitly printed in the given pages. Never calculate, convert, infer or fill gaps. If a value is absent, omit it.
- Keep each value and unit exactly as printed. Record the [PAGE n] number where it appears and a short verbatim quote copied character-for-character from that page.
- Map procurement methods to the instrument taxonomy:
  onsite = self-generation on company premises; ppa_physical = physical/direct PPA; ppa_virtual = virtual/financial PPA;
  green_tariff = utility green tariff/green pricing programs (incl. Korea 녹색프리미엄); unbundled_eac = separately purchased certificates (REC, I-REC, GO) not bundled with power;
  other = anything else (e.g. third-party REC bundled with power, utility default renewable mix claimed); unspecified = method not stated; total = total renewable electricity.
- Use geography 'GLOBAL' with level 'global' for company-wide figures. Use country codes only when the report states the figure for that country.
- Electricity-only: exclude renewable heat/fuel figures. If a table mixes energy types, take only electricity rows.
- Include every reported year shown (e.g. 3-year data tables)."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_pages(pdf_path: Path) -> list[str]:
    with pdfplumber.open(pdf_path) as pdf:
        return [(p.extract_text() or "") for p in pdf.pages]


def select_pages(pages: list[str]) -> list[int]:
    """1-based page numbers with enough RE keyword hits."""
    return [i + 1 for i, t in enumerate(pages) if len(_KW.findall(t)) >= MIN_HITS]


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s).lower()


def quote_on_page(quote: str, pages: list[str], page: int) -> bool:
    """인용문이 지정 페이지에 실제로 있는지 확인 (공백 무시). LLM 환각 방지용."""
    if not quote or not (1 <= page <= len(pages)):
        return False
    return _norm(quote) in _norm(pages[page - 1])


def call_claude(company: str, pages: list[str], page_nums: list[int]) -> Extraction:
    body = "\n\n".join(f"[PAGE {n}]\n{pages[n - 1]}" for n in page_nums)
    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        system=SYSTEM,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "high"},
        output_format=Extraction,
        messages=[{"role": "user", "content": f"Company: {company}\n\nReport pages:\n\n{body}"}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"Extraction refused: {msg.stop_details}")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("Output truncated (max_tokens). Split the report into smaller page batches.")
    return msg.parsed_output


def load_report(conn, company_id: str, pdf_path: Path, publication_year: int, batch_size: int = 40,
                json_path: Path | None = None) -> int:
    """PDF 한 개를 추출해 pending 상태로 적재. report_id 반환.
    json_path 를 주면 API 대신 그 파일(Extraction 스키마 JSON; 수작업/세션 추출본)을 사용한다."""
    sha = _sha256(pdf_path)
    if conn.execute("SELECT 1 FROM reports WHERE sha256=?", (sha,)).fetchone():
        raise ValueError(f"Already loaded: {pdf_path}")

    company = conn.execute("SELECT name FROM companies WHERE company_id=?", (company_id,)).fetchone()
    if not company:
        raise ValueError(f"Unknown company_id {company_id}; add it to config/competitors.yaml and run init.")

    pages = read_pages(pdf_path)
    if json_path is not None:
        results = [Extraction.model_validate_json(Path(json_path).read_text(encoding="utf-8"))]
        by = f"manual:{Path(json_path).name}"
    else:
        selected = select_pages(pages)
        if not selected:
            raise ValueError("No renewable-energy pages found (scanned PDF? OCR may be needed).")
        results = [call_claude(company["name"], pages, selected[i:i + batch_size])
                   for i in range(0, len(selected), batch_size)]
        by = f"llm:{MODEL}"

    cur = conn.execute(
        "INSERT INTO reports(company_id, publication_year, title, file_path, sha256, assurance, boundary_note) "
        "VALUES (?,?,?,?,?,?,?)",
        (company_id, publication_year, pdf_path.stem, str(pdf_path), sha,
         next((r.assurance for r in results if r.assurance), None),
         next((r.boundary_note for r in results if r.boundary_note), None)),
    )
    report_id = cur.lastrowid

    for r in results:
        for m in r.metrics:
            conn.execute(
                "INSERT INTO re_metrics(report_id, company_id, data_year, geography, geography_level, metric, instrument,"
                " value_reported, unit_reported, value_std, data_quality, page, quote, quote_verified, extracted_by)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,'A_reported',?,?,?,?)",
                (report_id, company_id, m.data_year, m.geography.upper() if m.geography_level != "site" else m.geography,
                 m.geography_level, m.metric, m.instrument if m.metric == "re_electricity" else None,
                 m.value, m.unit, standardize(m.metric, m.value, m.unit),
                 m.page, m.quote, int(quote_on_page(m.quote, pages, m.page)), by),
            )
        for t in r.targets:
            conn.execute(
                "INSERT INTO re_targets(report_id, company_id, geography, target_year, target_re_ratio, base_year,"
                " initiative, scope_note, page, quote, quote_verified, extracted_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (report_id, company_id, t.geography.upper(), t.target_year, t.target_re_ratio, t.base_year,
                 t.initiative, t.scope_note, t.page, t.quote, int(quote_on_page(t.quote, pages, t.page)), by),
            )
        for c in r.contracts:
            conn.execute(
                "INSERT INTO re_contracts(report_id, company_id, country, instrument, technology, capacity_mw, annual_mwh,"
                " term_years, start_year, counterparty, page, quote, quote_verified, extracted_by)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (report_id, company_id, c.country, c.instrument, c.technology, c.capacity_mw, c.annual_mwh,
                 c.term_years, c.start_year, c.counterparty, c.page, c.quote,
                 int(quote_on_page(c.quote, pages, c.page)), by),
            )
    conn.commit()
    return report_id
