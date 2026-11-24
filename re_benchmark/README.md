# 경쟁사 RE 벤치마크 (지속가능경영보고서 기반)

경쟁사 지속가능경영보고서에서 재생에너지(RE) 확보 정보를 추출해 DB에 쌓고,
우리 회사 RE 전략의 **경쟁사 BM 시나리오**로 사용한다.

- 대상 경쟁사: TSMC, SK hynix, Intel, Micron (`config/competitors.yaml`에서 추가)
- 자료원: **공개된 지속가능경영보고서만** (CDP 응답서는 비공개가 많아 제외)

## 신뢰성 원칙: 지표를 "만들지" 않고, 공시값을 "추적 가능하게" 쓴다

| 원칙 | 구현 |
|---|---|
| 모든 값에 근거를 남긴다 | `re_metrics.page`, `quote`, 보고서 `sha256` |
| LLM 추출값은 사람이 승인해야 사용한다 | `review_status` = pending → approved (reviewer 필수) |
| LLM 환각을 자동으로 거른다 | 인용문이 실제 그 페이지에 있는지 확인 (`quote_verified`) |
| 가공 수준을 등급으로 구분한다 | `A_reported` 공시값 그대로 / `B_derived` 공시값끼리 계산(산식 필수) / `C_estimated` 추정 (**시나리오에 사용하지 않음**) |
| 단위는 추측해서 환산하지 않는다 | 모르는 단위는 `value_std=NULL`로 두고 검토 대상에 올린다 |
| 국가별 값은 경쟁사가 그 국가 값을 공시한 경우에만 쓴다 | `mode=country`에서 공시가 없으면 GLOBAL로 대체하고, `basis` 열에 대체했다고 기록한다 |

### 시나리오 모드

- `global` (기본값): 경쟁사 전사 RE 비율의 실적과 목표 경로를 우리 사업장 전체에 적용한다. 공시값만 쓰므로 가장 방어하기 쉽다.
- `country`: 사업장 국가에 대해 경쟁사가 공시한 국가 값이 있을 때만 국가 경로를 쓰고, 없으면 global로 대체한다.
- `--method`: `average`(평균) / `median`(중앙값) / `leader`(최고치) / 특정 `company_id`
- 경로: 최근 실적에서 공시된 목표연도까지 선형으로 보간하고, 마지막 목표 이후에는 그 값을 유지한다. 보간 자체가 가정이므로 결과를 보고할 때 함께 밝혀야 한다.

## 사용법

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...            # 추출 단계에만 필요

python -m re_bm.cli init
python -m re_bm.cli extract intel data/reports/intel/2025_csr.pdf --year 2025
# API 없이: 직접 작성한 Extraction JSON 으로 적재 (data/extractions/*.json)
python -m re_bm.cli extract micron data/reports/micron/Micron_2026_Sustainability_Report.pdf --year 2026 --from-json data/extractions/micron_2026.json
python -m re_bm.cli review export        # data/review/*.csv 를 Excel로 검토
#   review_status 열에 approved 또는 rejected, reviewer 열에 검토자 이름 기입. 값이 틀렸으면 value_reported / unit_reported 를 수정
python -m re_bm.cli review import
python -m re_bm.cli derive               # 비율 미공시 항목: 승인된 총량으로 B_derived 비율 생성
python -m re_bm.cli scenario data/our_demand.csv --mode global --method average
```

`data/our_demand_template.csv`를 복사해 우리 사업장별 전력수요 전망을 넣는다.
`grid_ef_tco2_per_mwh`를 넣으면 시장기반 Scope 2 배출량도 계산한다. 이 계수는 국가별 잔여믹스 등 회사 기준에 맞는 값을 사용한다.

## 시나리오 계산 툴

```bash
python -m re_bm.tool      # tool/re_bm_tool.html 생성 (+ data/our_demand_dummy.csv)
```

브라우저에서 `tool/re_bm_tool.html`을 열면 승인된 경쟁사 데이터로 시나리오를 계산한다.
적용 기준(전사/국가별), 집계(평균/중앙값/최고치/개별 회사), 포함 회사, 요약 연도를 바꿀 수 있고,
사업장 수요 가정(현재 더미)을 화면에서 수정하면 바로 다시 계산된다. 계산 규칙은 `scenario.py`와 같다.

## 경쟁사 RE 수준 비교 (수요 없이 시나리오만)

우리 회사 수요·배출계수 없이, 경쟁사 공시값만으로 "누구 수준을 따라가면" 시나리오를 만든다.
시나리오: 업계 최고 / 업계 평균 / 업계 최저 (연도별, 포함 회사 기준) + TSMC·SK hynix·Intel·Micron 각 사 수준.
모두 전사 RE 전력 비율 기준이며, 국가별 공시값은 시나리오에 쓰지 않고 각주(regional_notes)로만 제공한다.

```bash
python -m re_bm.cli bm-levels --from-year 2025 --to-year 2040 [--companies tsmc,intel,...]
# → data/output/bm_levels.csv  (연도별 한 줄, 시나리오별 열 + 최고·최저를 정한 회사)
# → data/output/bm_levels.json (시나리오 패키지: 시나리오별 경로 + 근거 + 지역 각주)
```

화면 툴은 `python -m re_bm.tool`이 함께 만드는 `tool/bm_levels_tool.html`이다 (CSV / JSON 복사 가능).

## 구조

```
config/competitors.yaml   경쟁사 목록
db/schema.sql             companies, reports, re_metrics, re_targets, re_contracts
re_bm/extract.py          PDF 페이지 선별(키워드) → Claude 구조화 추출 → pending 적재
re_bm/validate.py         자동 점검(수단별 합계, 비율 정합성, 연도 간 급변) / B_derived 비율 산출
re_bm/review.py           검토 CSV 내보내기·반영
re_bm/scenario.py         BM 시나리오 계산
tests/                    API 호출 없이 실행하는 테스트 (더미 값)
```

## 한계와 주의사항

- 보고 경계(전사/일부 사업장), RE 정의(REC 포함 여부, 비전력 RE 포함 여부)가 회사마다 다르다. `reports.boundary_note`와 검토 메모에 남긴다.
- 스캔본 PDF는 텍스트 추출이 되지 않아 OCR이 필요하다.
- 조달 수단별 단가(비용) 계산은 아직 포함하지 않았다. 국가×수단별 단가 가정 테이블이 정해지면 추가한다.
