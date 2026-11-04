# GLP-1 drugs and psychiatric adverse event reports

Status: pipeline written and tested on fixture data (November 2026). Results, dashboard and findings are not in yet.

## Question

Are suicidal thoughts and behaviour, depression or anxiety reported more often than expected for semaglutide (Ozempic, Wegovy, Rybelsus), liraglutide (Victoza, Saxenda) and tirzepatide (Mounjaro, Zepbound), compared with SGLT2 inhibitors and with all other reports, in FDA FAERS and Health Canada's Canada Vigilance database? How much of any difference appears only after July 2023, when EMA began its review and the question reached the news?

## Reference results

EMA's Pharmacovigilance Risk Assessment Committee (PRAC) opened a review in July 2023 after the Icelandic Medicines Agency reported cases of suicidal thoughts and self-injury with liraglutide and semaglutide. In April 2024 PRAC concluded that the evidence from non-clinical studies, clinical trials and post-marketing surveillance did not support a causal link and that no change to the product information was needed.

FDA's preliminary evaluation (Drug Safety Communication, 11 January 2024) found no evidence of a causal link in FAERS reports or trials, while noting it could not rule out a small risk. On 13 January 2026 FDA asked for the suicidal behaviour and ideation warning to be removed from the Saxenda, Wegovy and Zepbound labels, citing a meta-analysis of 91 placebo-controlled trials (107,910 patients) and a Sentinel cohort of 2,243,138 new users that compared GLP-1 receptor agonists with SGLT2 inhibitors and found no increased risk of intentional self-harm.

A disproportionality study of the WHO database (Schoretsanitis et al., JAMA Network Open 2024;7(8), doi:10.1001/jamanetworkopen.2024.23385) found a reporting signal for semaglutide and suicidal ideation (ROR 1.45, 95% CI 1.18 to 1.77) against all other drugs, and larger RORs against dapagliflozin, metformin and orlistat.

This project asks whether FAERS and Canada Vigilance show the same pattern, and whether the signal holds against an active comparator and outside the period of media attention.

## Data

FAERS quarterly ASCII files, 2019 Q1 to the latest published quarter, and the Canada Vigilance extract dated 30 June 2026. Both are the same downloads used by [Safety Signal Explorer](https://github.com/mgoldenitz/safety-signal-explorer); this pipeline reads them from `~/ssx_data/raw` and builds its own database in `~/glp1_data`.

## Method

The pipeline is adapted from Safety Signal Explorer: FAERS de-duplication by latest case version, removal of FDA-deleted cases, primary and secondary suspect drugs only, whole-word drug matching on active ingredient and brand name, and ROR, PRR (Evans criteria) and IC025 from 2 x 2 tables.

Exposures: semaglutide, liraglutide and tirzepatide, each split by the indication on the drug row (type 2 diabetes, weight management, other, unknown; the brand decides when no indication is given), compounded semaglutide and tirzepatide, and the GLP-1 class (adding dulaglutide, exenatide and lixisenatide).

Backgrounds: all other reports; SGLT2 inhibitors (empagliflozin, dapagliflozin, canagliflozin, ertugliflozin, bexagliflozin); and SGLT2 inhibitors given for type 2 diabetes only, since empagliflozin and dapagliflozin are also used for heart failure and kidney disease. SGLT2 inhibitors are the active comparator because they treat the same disease, came to market in a similar period and have no known psychiatric effect.

Outcomes: three groups of MedDRA preferred terms written before any data were loaded (suicidal and self-injurious behaviour, depression, anxiety; listed in `scripts/common.py`), plus each term on its own. MedDRA's Standardised MedDRA Queries need a licence, so the groups are an approximation.

Notoriety bias: the psychiatric results are repeated for reports first received before July 2023 and from July 2023 onward, with the background limited to the same period.

Validation, run before any psychiatric result is read: label reactions as positive controls (nausea, vomiting, decreased appetite, pancreatitis, gallbladder disease and injection site reactions for GLP-1 drugs; ketoacidosis, genital fungal infection and Fournier's gangrene for SGLT2 inhibitors), comparator checks (nausea should be flagged against SGLT2 inhibitors; ketoacidosis should not), and four negative controls picked from a fixed candidate list by a report-count rule.

## Running it

In WSL, from the repo folder:

```
~/brainenv/bin/python -m pytest -q tests
bash run_all.sh ~/brainenv/bin/python
```

Steps: `01_download_faers.py` (only quarters not already in `~/ssx_data/raw/faers`), `02_load_faers.py`, `03_deduplicate.py`, `04_signals.py`, `05_validate.py` (stops the run if a positive control fails), `06_canada_vigilance.py`, `07_export.py`. Set `GLP_DATA`, `GLP_FAERS_RAW` or `GLP_CV_RAW` to use other folders.

## Outputs

`outputs/psych_signals.csv` is the main Tableau source (psychiatric terms and groups, both databases, all backgrounds and periods). `signals.csv` and `cv_signals.csv` hold every drug-reaction pair with at least 3 reports. Also `validation.csv`, `drugs.csv`, `term_groups.csv`, `reports_by_quarter.csv`, `reporters.csv`, `demographics.csv`, `outcomes.csv`, `cv_reports_by_year.csv`, `pt_soc.csv`, `data_summary.csv`.

## Limitations

Spontaneous reports show association, not incidence or causation, and there is no count of people exposed. People treated for obesity have higher rates of depression than people treated for diabetes, so the weight-management subgroups are confounded by indication; the SGLT2 comparator is a diabetes population. Media coverage from July 2023 can raise reporting by itself. Compounded products sold during the 2022 to 2025 shortages may be under-reported or named inconsistently. The term groups and indication rules approximate MedDRA.
