# Carbon Standards Advisor - Source Map

Version: 0.1  
Prepared: 2026-08-05  
Purpose: Route questions to the correct source, distinguish authority levels and versions, and prevent cross-framework misapplication.

## 1. Core routing map

| Question area | Primary pack | Primary sources | Secondary / supporting sources |
|---|---|---|---|
| Korea ETS emissions calculation and reporting | `01_KETS_Pack.pdf` | KETS Annex 6 | ES 13501; facility-specific emission factor guide |
| Semiconductor F-gas / N2O inventory | `02_IPCC_2019_Pack.pdf` | IPCC 2019 Refinement Vol.3 Ch.6 Electronics | GHG Protocol Corporate Standard |
| Refrigerants / HFCs | `02_IPCC_2019_Pack.pdf` | IPCC 2019 Refinement Vol.3 Ch.7 ODS Substitutes | GHG Protocol Corporate Standard |
| SF6 and other product uses | `02_IPCC_2019_Pack.pdf` | IPCC 2019 Refinement Vol.3 Ch.8 | GHG Protocol Corporate Standard |
| Wastewater | `02_IPCC_2019_Pack.pdf` | IPCC 2019 Refinement Vol.5 Ch.6 | GHG Protocol Corporate Standard |
| GWP lookup | `03_GWP_Data.xlsx` | AR4/AR5/AR6 lookup dataset | Verify against the relevant authoritative IPCC source when the exact GWP is consequential |
| Corporate GHG inventory boundary | `04_GHG_Protocol_Pack.pdf` | GHG Protocol Corporate Standard | IFRS S2 where disclosure requirements also apply |
| Scope 2 / market-based / steam, heat, cooling | `04_GHG_Protocol_Pack.pdf` | GHG Protocol Scope 2 Guidance | IFRS S2 / KSSB for disclosure |
| Scope 3 | `04_GHG_Protocol_Pack.pdf` | Corporate Value Chain (Scope 3) Standard | IFRS S2 / KSSB for disclosure |
| International climate disclosure | `05_Disclosure_Pack.pdf` | IFRS S2 | IFRS GHG educational material |
| Korean climate disclosure | `05_Disclosure_Pack.pdf` | KSSB Standard No.2 | IFRS S2 where useful for comparison |
| Net-zero / neutralization / BVCM / claims | `06_NetZero_Pack.pdf` | Applicable SBTi Corporate Net-Zero Standard | NIER commentary on ISO 14068-1 |
| Korea climate change impact assessment | `07_ClimateImpact_Pack.pdf` | Applicable law/regulatory annex | 2026-04 explanatory guide |

## 2. Authority hierarchy

When sources conflict, do not treat all uploaded materials as equal.

1. Current applicable law/regulation and current effective normative standard.
2. Primary methodology or accounting standard issued by the responsible standard setter.
3. Official application guidance or amendments that apply to the primary standard.
4. Official educational/explanatory material.
5. Secondary commentary, summaries, and compiled datasets.

If a source is older, superseded, not yet effective, or only explanatory, label that status explicitly in the answer.

## 3. Source registry

### KETS Pack

**KETS-01 - Korea ETS Annex 6**  
Role: Primary regulatory source for detailed emissions calculation/reporting requirements.  
Topics: Emission calculation, activity data, rounding, parameters, reporting.  
Currency rule: If current legal applicability matters, verify the latest official legal text before concluding.

**KETS-02 - ES 13501 (2023)**  
Role: Korean greenhouse-gas process test standard.  
Topics: FTIR measurement of N2O, HFCs, PFCs, SF6 and NF3; POU and house-scrubber measurement terminology.

**KETS-03 - Facility-Specific Emission Factor Development Guide (2024-02)**  
Role: Implementation/development guidance.  
Topics: Tier 3 factor development and reporting.

### IPCC 2019 Pack

**IPCC-01 - 2019 Refinement Vol.3 Ch.6 Electronics Industry Emissions**  
Role: Primary IPCC methodology source.  
Topics: Semiconductor F-gases, process types, by-products, Tier methods and abatement.

**IPCC-02 - 2019 Refinement Vol.3 Ch.7 ODS Substitutes**  
Role: Primary IPCC methodology source.  
Topics: HFCs/refrigerants and substitutes for ozone-depleting substances.

**IPCC-03 - 2019 Refinement Vol.3 Ch.8 Other Product Manufacture and Use**  
Role: Primary IPCC methodology source.  
Topics: Other product uses including relevant SF6 applications.

**IPCC-04 - 2019 Refinement Vol.5 Ch.6 Wastewater Treatment and Discharge**  
Role: Primary IPCC methodology source.  
Topics: Wastewater GHG emissions.

### GWP Data

**GWP-01 - IPCC_AR4-AR6_GWPs.xlsx**  
Role: Lookup dataset compiled across AR4, AR5 and AR6 time horizons.  
Dataset DOI recorded in workbook: https://doi.org/10.23719/1529821  
Important: Treat the workbook as a lookup aid, not as a substitute for an authoritative IPCC citation when an exact GWP value is material to a formal conclusion.

### GHG Protocol Pack

**GHGP-01 - GHG Protocol Corporate Accounting and Reporting Standard, Revised Edition**  
Role: Primary corporate GHG accounting standard.  
Topics: Organizational boundary, operational boundary, inventory design, Scope 1-3 classification, reporting.

**GHGP-02 - GHG Protocol Scope 2 Guidance**  
Role: Primary Scope 2 guidance and amendment to the Corporate Standard.  
Topics: Location-based and market-based methods, contractual instruments, steam, heat and cooling, dual reporting.

**GHGP-03 - Corporate Value Chain (Scope 3) Accounting and Reporting Standard**  
Role: Primary Scope 3 standard.  
Topics: Scope 3 categories, minimum boundaries, data, allocation, targets and reporting.

### Disclosure Pack

**DISC-01 - IFRS S2 Climate-related Disclosures, 2026 edition**  
Role: Primary ISSB climate-disclosure standard.  
Note: The provided edition incorporates the December 2025 amendments to GHG emissions disclosures.

**DISC-02 - Greenhouse Gas Emissions Disclosure Requirements Applying IFRS S2, May 2025**  
Role: IFRS Foundation educational material.  
Important: The document states that it is not part of IFRS Standards and does not add to or change the requirements.

**DISC-03 - KSSB Climate-related Disclosures Standard No.2, adopted 2026-02-26**  
Role: Korean climate-disclosure standard.  
Currency rule: Check Appendix C/D and current official requirements for effective date, transition and voluntary/mandatory applicability.

### Net Zero Pack

**NZ-01 - SBTi Corporate Net-Zero Standard v1.3.1, April 2026**  
Role: SBTi Corporate Net-Zero Standard version effective from 2026-04-14.  
Use: Determine whether it is the current applicable version by comparing the question date with successor effective dates.

**NZ-02 - SBTi Corporate Net-Zero Standard v2.0, June 2026**  
Release date: 2026-06-11.  
Effective date: 2027-02-01.  
Important: Before the effective date, distinguish future v2.0 requirements from requirements under the then-current standard.

**NZ-03 - NIER Commentary on ISO 14068-1 Carbon Neutrality Requirements, 2025-12**  
Role: Secondary Korean explanatory material.  
Important: This is NOT the ISO 14068-1 normative standard text. Do not attribute commentary wording directly to ISO unless verified against the ISO standard.

### Climate Impact Pack

**CIA-01 - Climate Change Impact Assessment Methods Guide, 2026-04**  
Role: Latest provided explanatory guide.  
Important: The guide explicitly states that it is reference material and should not be treated as a binding administrative guideline.

**CIA-02 - Annex 1, Scale Criteria for Plans and Projects Subject to Climate Change Impact Assessment**  
Role: Regulatory annex for applicability/scale criteria.  
Currency rule: Verify the latest official regulatory text when making a current legal applicability conclusion.

## 4. Deliberately excluded from v0.1 Knowledge

- `ghg-protocol-기업온실가스회계및보고표준.pdf`: retained as a useful Korean translation/reference, but excluded from the GPT Knowledge set to reduce duplicated retrieval and conflicting page citations with the English primary source.
- `기후변화영향평가 방법 등에 관한 안내서(2023.3.).pdf`: superseded for this project by the provided 2026-04 guide.

## 5. Citation rule for merged packs

Each merged pack contains a divider page before every original source.

When answering:

- Cite the original source title, version/date, section/paragraph/table, and original printed page number.
- Never cite the merged pack PDF page number as if it were the original source page.
- If the original printed page cannot be verified, cite the section/paragraph/table and say that the page number was not reliably identified.
- Never invent a page, paragraph, clause, table, effective date, or quotation.

