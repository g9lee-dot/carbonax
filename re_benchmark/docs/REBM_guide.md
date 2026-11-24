# 경쟁사 BM 시나리오 생성기 (REBM) 설명서

2026-11-24 기준

## 1. 개요

REBM은 경쟁사 지속가능경영보고서에서 재생에너지(RE) 확보 정보를 추출해 근거와 함께 DB로 저장하고, 이를 우리 회사 RE 전략의 '경쟁사 BM 시나리오'로 만드는 도구입니다. 산출물은 연도·국가(사업장)별 목표 RE 비율과 필요 RE 물량, 시장기반 Scope 2 배출량입니다.

- 대상 경쟁사: TSMC, SK hynix, Intel, Micron (`config/competitors.yaml`에 추가하면 확장 가능)
- 자료원: 공개된 지속가능경영보고서만 사용 (CDP 응답서는 비공개가 많아 제외)
- 위치: GitHub `g9lee-dot/carbonax`, 브랜치 `claude/renewable-energy-data-extraction-w445pd`, 폴더 `re_benchmark/`
- 구현: Python 3, SQLite, pdfplumber, Anthropic SDK(추출 단계만), 단일 HTML 계산 툴

| 구성요소 | 상태 | 비고 |
| --- | --- | --- |
| 보고서 수집 (4개사) | 완료 | TSMC는 Climate and Nature Report로 대체 |
| 페이지 선별 · 자동 점검 | 완료 | |
| 수치 추출 | JSON 수작업 완료, API 자동추출 대기 | API 키 연결 시 같은 경로로 동작 |
| 사람 검토 | 일괄 승인(가정) | 실제 검토 전 |
| 시나리오 계산 (CLI · 툴) | 완료 | 우리 사업장 수요·배출계수는 더미 |

## 2. 신뢰성 원칙

경쟁사 수치를 추정해서 만들지 않고, 공시된 값만 추적 가능하게 씁니다. 시나리오 결과의 모든 숫자는 보고서 페이지와 원문 인용까지 거슬러 올라갈 수 있습니다.

| 원칙 | 구현 |
| --- | --- |
| 모든 값에 근거를 남긴다 | 값마다 보고서(sha256), 페이지, 원문 인용 저장 |
| 추출값의 환각을 자동으로 거른다 | 인용문이 해당 페이지 텍스트에 실제로 있는지 대조(quote_verified) |
| 가공 수준을 등급으로 구분한다 | A 공시값 그대로 / B 공시값끼리 계산(산식 필수) / C 추정(시나리오 미사용) |
| 사람이 승인한 값만 쓴다 | pending → approved(검토자 필수) 상태만 시나리오 반영 |
| 단위는 추측해서 환산하지 않는다 | 모르는 단위는 표준값을 비워 검토 대상으로 넘김 (예: MTCO2e는 회사마다 뜻이 달라 자동 환산 안 함) |
| 국가별 값은 공시된 경우만 쓴다 | 경쟁사가 그 국가를 직접 공시하지 않았으면 전사 값으로 대체하고, 결과에 '전사 대체'로 표시 |

연도별 경로를 목표까지 직선으로 잇는 것(보간)은 우리 쪽 가정이므로, 보고 시 함께 밝힙니다.

## 3. 전체 워크플로우

```mermaid
flowchart TB
  subgraph build[데이터 구축]
    A[① 보고서 수집<br/>4개사 지속가능경영보고서 PDF] --> B[② RE 페이지 선별<br/>키워드 2회 이상, 예: 132쪽 → 11쪽]
    B --> C[③ 수치 추출<br/>JSON 직접 작성 현재 사용<br/>Claude API 자동 추출 연결 대기]
    C --> D[④ 자동 점검<br/>원문 인용 대조 · 단위 · 합계 · 급변]
    D --> E[⑤ 사람 검토<br/>승인/반려, 현재 일괄 승인 가정]
    E --> F[(⑥ 벤치마크 DB<br/>값마다 페이지 · 인용 · 등급 A/B/C)]
  end
  subgraph scen[시나리오 계산]
    G[우리 사업장 수요 · 배출계수<br/>현재 더미 → 사내 값으로 교체] --> H[⑦ 시나리오 엔진<br/>경로 · 집계 · 적용 · 계산]
    H --> I[결과 CSV<br/>re_bm.cli scenario]
    H --> J[계산 툴<br/>tool/re_bm_tool.html]
    I -.-> K[RE 시뮬레이터<br/>연계 검토 대상]
    J -.-> K
  end
  F -- 승인된 A·B 값만 --> H
```

왼쪽(위) 묶음은 보고서에서 데이터를 쌓는 단계, 오른쪽(아래) 묶음은 그 데이터로 시나리오를 계산하는 단계입니다. 점선은 아직 구현되지 않은 연계입니다. 같은 그림의 HTML 버전은 `docs/workflow.html`입니다.

## 4. 데이터 모델

SQLite 파일 하나(`data/re_benchmark.db`)에 5개 테이블이 있습니다. 스키마 정의는 `db/schema.sql`입니다.

| 테이블 | 내용 | 주요 컬럼 |
| --- | --- | --- |
| companies | 경쟁사 목록 | company_id, name, hq_country |
| reports | 적재한 보고서 | company_id, publication_year, file_path, sha256, assurance, boundary_note |
| re_metrics | 실적 지표 | data_year, geography, geography_level, metric, instrument, value_reported, unit_reported, value_std, data_quality, page, quote, quote_verified, review_status |
| re_targets | RE 목표 | geography, target_year, target_re_ratio, base_year, initiative, scope_note, page, quote |
| re_contracts | 개별 PPA 등 계약 | country, instrument, technology, capacity_mw, annual_mwh, start_year, counterparty |

**지표(metric) 종류:** total_electricity(총 전력), re_electricity(RE 전력, 수단별 또는 합계), re_ratio(RE 비율 %), scope2_market_based, scope2_location_based.

**지역(geography):** GLOBAL(전사), ISO 국가코드(KR, CN, US, TW 등), 권역(예: TSMC OVERSEAS), 사업장명.

**조달수단(instrument) 분류.** GHG Protocol Scope 2 Guidance와 RE100 기준에 맞춘 표준 분류입니다. RE 시뮬레이터와 맞춰야 할 핵심 항목입니다.

| 코드 | 의미 |
| --- | --- |
| onsite | 사업장 내 자가발전 |
| ppa_physical | 물리적(직접) PPA |
| ppa_virtual | 가상(금융) PPA |
| green_tariff | 유틸리티 녹색요금 (한국 녹색프리미엄 포함) |
| unbundled_eac | 별도 구매 인증서 (REC, I-REC, GO) |
| other / unspecified / total | 기타 / 수단 미기재 / RE 총량 |

**단위 표준:** 전력 MWh, 비율 %, 배출량 tCO2e. 보고서 원래 값과 단위(value_reported, unit_reported)도 함께 보관합니다.

## 5. 현재 적재 데이터

4개사 5개 보고서에서 지표 66건, 목표 7건, 계약 7건을 적재했고, 인용문은 전 항목이 원문 페이지에서 확인됐습니다. 2025년 전사 RE 비율은 Intel 99%, SK hynix 31.0%, TSMC 20.1%, Micron 13%입니다.

**전사 RE 전력 비율 실적 (%)**

| 회사 | 2021 | 2022 | 2023 | 2024 | 2025 |
| --- | --- | --- | --- | --- | --- |
| Intel | 80 | 93 | 99 | 98 | 99 |
| SK hynix | – | 29.6 | 30.0 | 29.9 | 31.0 |
| TSMC | – | – | – | – | 20.1 |
| Micron | – | 2 | 4 | 9 | 13 |

출처: 각사 2025~2026 지속가능경영보고서(re_metrics). Micron은 회계연도 기준.

**RE 목표**

| 회사 | 범위 | 목표연도 | 목표 RE 비율 | 근거 |
| --- | --- | --- | --- | --- |
| Intel | 전사 | 2030 | 100% | CSR 2025-26 p.36 |
| TSMC | 전사 | 2030 | 60% | Climate and Nature Report p.39 (연도는 p.5 로드맵 기준, 본 보고서로 확인 필요) |
| TSMC | 전사 | 2040 | 100% | p.15 |
| SK hynix | 전사 | 2026 | 31% | 2026 보고서 p.25 |
| SK hynix | 전사 | 2030 | 33% | p.23 |
| SK hynix | 전사 | 2050 | 100% | p.23 (RE100) |
| Micron | 미국 | 2025 | 100% | 2026 보고서 p.35 (달성). 전사 수치 목표 없음 |

**국가별 공시 RE 비율 (2025)**

| 국가·지역 | 공시 회사와 값 |
| --- | --- |
| 중국 | Intel 100%, Micron 100%, SK hynix 100% |
| 미국 | Intel 100%, Micron 100% |
| 대만 | TSMC 11.5% |
| 말레이시아 | Intel 100%, Micron 100% |
| 아일랜드·이스라엘·폴란드·베트남 | Intel 100% |
| 코스타리카 / 인도 | Intel 97% / 0% |
| TSMC 해외 자회사(국가 미기재) | TSMC 100% |
| 한국 | 공시 없음 (SK hynix 31%는 한국+중국 전사 값) |

**보고 경계 주의사항**

- Micron: 회계연도 기준(FY25 = 2024.9~2025.8). 13%에는 고객사에 우선 배분한 683,641 MWh 포함, 미배분 RE는 5.9%.
- SK hynix: 데이터 범위 이천·청주·분당·서울·우시·충칭. Scope 2 표는 location-based, market-based는 Scope 1+2 합계만 공시.
- TSMC: 본 Sustainability Report 미확보. 총 전력사용량·Scope 2 미추출.
- Intel: 역년 기준. 조달수단별 물량은 4개사 모두 미공시.

## 6. 시나리오 계산 로직

경쟁사별 RE 비율 경로를 만들고, 이를 집계한 벤치마크 비율을 우리 사업장 수요에 곱합니다. 구현은 `re_bm/scenario.py`(CLI)와 `tool/re_bm_tool.html`(툴)이며, 두 결과는 더미 수요 75건에서 1 MWh 이내로 일치합니다.

1. **경로 생성 (회사·지역별):** 실적 연도는 실적값. 마지막 실적 이후는 공시 목표연도까지 선형 보간하고, 마지막 목표 이후에는 그 값을 유지. 목표가 없는 회사는 최근 실적을 유지.
2. **집계 (method):** 평균(average), 중앙값(median), 최고치(leader), 특정 회사(company_id). 포함 회사를 고를 수 있음.
3. **적용 (mode):** global = 전사 경로를 모든 사업장에 적용. country = 사업장 국가를 공시한 회사가 있으면 국가 경로, 없으면 전사 경로로 대체.
4. **계산:** 아래 식을 연도·사업장마다 적용. 조달수단별 배분은 경쟁사 수단별 물량 공시가 없어 현재는 unspecified 처리.

```
RE[y,s]     = D[y,s] × BM[y, g(s)] / 100
S2_MB[y,s]  = (D[y,s] − RE[y,s]) × EF[s]
```

D = 사업장 전력수요(MWh), BM = 벤치마크 RE 비율(%), g(s) = 적용 지역(국가 또는 GLOBAL), EF = 배출계수(tCO2/MWh).

**입력: 사업장 수요 CSV** (`data/our_demand_template.csv` 형식, 현재 값은 더미)

```csv
year,site,country,demand_mwh,grid_ef_tco2_per_mwh
2030,KR_Fab,KR,22510176,0.4567
2030,US_Austin,US,2601510,0.37
```

**출력: 결과 CSV** (`re_bm.cli scenario`, 툴의 'CSV 복사'도 동일 항목)

| 컬럼 | 의미 |
| --- | --- |
| year, site, country, demand_mwh | 입력 그대로 |
| bm_re_ratio_pct | 적용된 벤치마크 RE 비율 |
| re_mwh, re_mwh_<수단> | 필요 RE 물량과 수단별 배분 |
| scope2_mb_tco2e | 시장기반 Scope 2 |
| basis | global / country_reported / fallback_global |
| bm_method, bm_companies | 집계 방법과 반영된 회사 |

**더미 기준 결과 (2030년, 평균):** 전사 기준 벤치마크 51.5%, 필요 RE 약 16.0 TWh. 국가별 기준 수요 가중 64.9%, 약 20.2 TWh(중국·미국 100%, 한국은 전사 51.5%로 대체).

## 7. RE 시뮬레이터 연계 검토 포인트

REBM은 "어느 수준까지 가야 하는가(경쟁사 근거)"를, RE 시뮬레이터는 "어떻게, 얼마에 갈 수 있는가"를 담당하도록 나누는 것을 제안합니다. 아래는 RE 시뮬레이터 코드를 보지 않고 작성한 가정 기반 안입니다.

**연계 시나리오 후보**

| 연계 | 흐름 | 얻는 것 |
| --- | --- | --- |
| 목표 주입 (우선 권장) | REBM 연도·국가별 목표 RE 비율 → 시뮬레이터 목표 제약 | 경쟁사 수준 추종 시 필요 물량·수단 구성·비용 |
| 갭 분석 | 시뮬레이터 국가별 확보 가능 최대치 ↔ REBM 경로 | 따라갈 수 없는 국가·연도와 부족분 |
| 가정 검증 | REBM 계약 사례(re_contracts) → 시뮬레이터 수단 가정 점검 | 규모·형태 참고값 (예: Micron 텍사스 VPPA 238MW, SK hynix 국내 수력 PPA) |
| 비교 시각화 | 시뮬레이터 결과를 REBM 경로 차트에 중첩 | 우리 계획 vs 경쟁사 경로 |

**인터페이스 계약안 (파일 교환, JSON).** REBM이 내보내고 시뮬레이터가 읽는 형태입니다. 아직 구현되지 않았으며, 검토 후 `re_bm.cli export-scenario`로 만들 예정입니다.

```json
{
  "scenario_id": "competitor_bm_average_country",
  "source": "REBM",
  "method": "average", "mode": "country",
  "companies": ["tsmc", "skhynix", "intel", "micron"],
  "generated_at": "2026-11-23", "data_status": "approved (assumed)",
  "targets": [
    {"year": 2030, "country": "KR", "re_ratio_pct": 51.5, "basis": "fallback_global", "evidence_ids": [12, 31]},
    {"year": 2030, "country": "US", "re_ratio_pct": 100, "basis": "country_reported"}
  ],
  "reference_contracts": [
    {"company": "micron", "country": "US", "instrument": "ppa_virtual", "capacity_mw": 238}
  ]
}
```

**사내망에서 확인할 것**

- [ ] 시뮬레이터가 목표를 비율(%)로 받는지, 물량(MWh)으로 받는지
- [ ] 목표 단위가 국가별인지 사업장별인지, 연도 범위(현재 2026~2040)
- [ ] 조달수단 분류가 4장의 7개 코드와 1:1로 대응되는지 (녹색프리미엄·REC 구분 포함)
- [ ] 전력수요·배출계수의 기준 출처를 시뮬레이터와 공유할지 (REBM의 더미를 사내 값으로 대체)
- [ ] 시뮬레이터가 비용·확보 한도 결과를 내는지 (갭 분석 가능 여부)
- [ ] 연계 방식: 파일 교환 / 공유 DB / API 중 사내 환경에서 가능한 것
- [ ] 사내망 반입 제약: Anthropic API 사용 가능 여부 (불가 시 JSON 수작업 경로로 운영)

## 8. 한계와 후속 과제, 파일 위치

**현재 한계**

- 한국 사업장에 적용할 경쟁사 국가별 공시값이 없어 전사 값으로 대체됩니다.
- 조달수단별 물량을 공시한 경쟁사가 없어 수단 구성은 벤치마크하지 못합니다(정성 정보만 보관).
- 추출값은 사람 검토 없이 일괄 승인된 상태입니다.
- TSMC는 본 보고서가 없어 목표연도(2030년 60%) 확인이 필요합니다.
- 경로의 직선 보간은 가정입니다. 회계연도(Micron)와 역년 차이도 보정하지 않았습니다.
- 조달수단별 비용은 계산하지 않습니다(RE 시뮬레이터 연계 대상).

**후속 과제**

- [ ] 추출값 실제 검토 (`review export` → 승인/반려 → `review import`)
- [ ] 사내 전력수요 전망·배출계수로 더미 대체
- [ ] RE 시뮬레이터 입력 형식 확인 후 `export-scenario` 구현
- [ ] Anthropic API 연결로 추출 자동화, 경쟁사 추가 시 매년 갱신

**파일·명령어 (`re_benchmark/` 기준)**

| 구분 | 위치 / 명령 |
| --- | --- |
| 경쟁사 목록 | `config/competitors.yaml` |
| 보고서·출처 | `data/reports/<회사>/`, `data/reports/SOURCES.md` |
| 추출 결과(JSON) | `data/extractions/*.json` |
| DB·스키마 | `data/re_benchmark.db`, `db/schema.sql` |
| 추출·적재 | `python -m re_bm.cli extract <회사> <PDF> --year <발간연도> [--from-json <파일>]` |
| 검토 | `python -m re_bm.cli review export` / `import` (결과: `data/review/`) |
| 비율 산출(B등급) | `python -m re_bm.cli derive` |
| 시나리오 CSV | `python -m re_bm.cli scenario <수요CSV> --mode global\|country --method average\|median\|leader\|<회사>` |
| 계산 툴 | `python -m re_bm.tool` → `tool/re_bm_tool.html` |
| 테스트 | `python -m pytest tests` |
| 워크플로우 그림 | `docs/workflow.html` |

## 9. 내려받기

레포는 공개(public) 상태이며, 작업물은 기본 브랜치가 아닌 아래 브랜치에 있습니다.

- 브랜치 페이지: https://github.com/g9lee-dot/carbonax/tree/claude/renewable-energy-data-extraction-w445pd/re_benchmark
- 전체 ZIP: https://github.com/g9lee-dot/carbonax/archive/refs/heads/claude/renewable-energy-data-extraction-w445pd.zip
- git: `git clone -b claude/renewable-energy-data-extraction-w445pd https://github.com/g9lee-dot/carbonax.git`
- 이 문서 원문(raw): https://raw.githubusercontent.com/g9lee-dot/carbonax/claude/renewable-energy-data-extraction-w445pd/re_benchmark/docs/REBM_guide.md

연계 검토에 필요한 최소 파일은 `re_bm/scenario.py`, `db/schema.sql`, `data/re_benchmark.db`, `data/our_demand_template.csv`, 이 문서입니다. 보고서 PDF(약 55MB)는 근거 확인이 필요할 때만 받으면 됩니다.
