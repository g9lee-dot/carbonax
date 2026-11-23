-- 경쟁사 재생에너지(RE) 벤치마크 DB 스키마 (SQLite)
-- 원칙: 모든 수치는 근거(보고서, 페이지, 원문 인용)와 데이터 품질 등급을 함께 저장한다.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS companies (
    company_id   TEXT PRIMARY KEY,          -- 예: tsmc, skhynix, intel, micron
    name         TEXT NOT NULL,
    hq_country   TEXT,                      -- ISO 3166-1 alpha-2
    peer_group   TEXT DEFAULT 'semiconductor'
);

CREATE TABLE IF NOT EXISTS reports (
    report_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id        TEXT NOT NULL REFERENCES companies(company_id),
    publication_year  INTEGER NOT NULL,     -- 보고서 발간연도
    title             TEXT,
    file_path         TEXT NOT NULL,
    sha256            TEXT NOT NULL UNIQUE, -- 동일 파일 중복 적재 방지 및 원본 추적
    assurance         TEXT,                 -- 제3자 검증 여부/기관/수준 (보고서 기재 내용)
    boundary_note     TEXT,                 -- 보고 경계(전사/일부 사업장 등)
    loaded_at         TEXT DEFAULT (datetime('now'))
);

-- 실적 지표. 수단별 RE 사용량은 metric='re_electricity' + instrument 로 표현한다.
CREATE TABLE IF NOT EXISTS re_metrics (
    metric_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id        INTEGER NOT NULL REFERENCES reports(report_id),
    company_id       TEXT NOT NULL REFERENCES companies(company_id),
    data_year        INTEGER NOT NULL,
    geography        TEXT NOT NULL,         -- 'GLOBAL', ISO 국가코드(KR, TW, US...), 또는 사업장명
    geography_level  TEXT NOT NULL CHECK (geography_level IN ('global','region','country','site')),
    metric           TEXT NOT NULL CHECK (metric IN (
                        'total_electricity',     -- 총 전력사용량
                        're_electricity',        -- RE 전력사용량 (instrument 별 또는 합계)
                        're_ratio',              -- RE 비율 (%)
                        'scope2_market_based',   -- tCO2e
                        'scope2_location_based'  -- tCO2e
                     )),
    instrument       TEXT CHECK (instrument IN (
                        'total','onsite','ppa_physical','ppa_virtual',
                        'green_tariff','unbundled_eac','other','unspecified')),
    value_reported   REAL NOT NULL,         -- 보고서에 적힌 값 그대로
    unit_reported    TEXT NOT NULL,         -- 보고서에 적힌 단위 그대로
    value_std        REAL,                  -- 표준단위 환산값 (전력=MWh, 비율=%, 배출량=tCO2e)
    data_quality     TEXT NOT NULL CHECK (data_quality IN ('A_reported','B_derived','C_estimated')),
    page             INTEGER,               -- 근거 페이지 (PDF 기준, 1부터)
    quote            TEXT,                  -- 원문 인용
    quote_verified   INTEGER DEFAULT 0,     -- 인용문이 해당 페이지 텍스트에 실제로 있는지 자동 확인 결과
    derivation_note  TEXT,                  -- B/C 등급일 때 산출식·가정 (필수)
    review_status    TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
    reviewer         TEXT,
    review_note      TEXT,
    extracted_by     TEXT,                  -- 'llm:<model>' 또는 'manual'
    extracted_at     TEXT DEFAULT (datetime('now')),
    CHECK (data_quality = 'A_reported' OR derivation_note IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS re_targets (
    target_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id        INTEGER NOT NULL REFERENCES reports(report_id),
    company_id       TEXT NOT NULL REFERENCES companies(company_id),
    geography        TEXT NOT NULL DEFAULT 'GLOBAL',
    target_year      INTEGER NOT NULL,
    target_re_ratio  REAL NOT NULL,         -- %
    base_year        INTEGER,
    initiative       TEXT,                  -- RE100 등
    scope_note       TEXT,                  -- 적용 범위·조건
    page             INTEGER,
    quote            TEXT,
    quote_verified   INTEGER DEFAULT 0,
    review_status    TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
    reviewer         TEXT,
    review_note      TEXT,
    extracted_by     TEXT,
    extracted_at     TEXT DEFAULT (datetime('now'))
);

-- 개별 PPA 등 조달 계약 (정성 정보 위주, 시나리오 직접 입력값은 아님)
CREATE TABLE IF NOT EXISTS re_contracts (
    contract_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id        INTEGER NOT NULL REFERENCES reports(report_id),
    company_id       TEXT NOT NULL REFERENCES companies(company_id),
    country          TEXT,
    instrument       TEXT,
    technology       TEXT,                  -- solar, wind_onshore, wind_offshore ...
    capacity_mw      REAL,
    annual_mwh       REAL,
    term_years       REAL,
    start_year       INTEGER,
    counterparty     TEXT,
    page             INTEGER,
    quote            TEXT,
    quote_verified   INTEGER DEFAULT 0,
    review_status    TEXT NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending','approved','rejected')),
    extracted_by     TEXT,
    extracted_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS ix_metrics_lookup ON re_metrics(company_id, data_year, geography, metric);
