# GLP-1 drugs and psychiatric adverse event reports

Status: first full run 3 November 2026. Findings below.

Interactive dashboard: [GLP-1 Drugs and Psychiatric Adverse Event Reports on Tableau Public](https://public.tableau.com/app/profile/michael.goldenitz/viz/GLP-1DrugsandPsychiatricAdverseEventReports/GLP-1psychiatricsignals)

## Question

Are suicidal thoughts and behaviour, depression or anxiety reported more often than expected for semaglutide (Ozempic, Wegovy, Rybelsus), liraglutide (Victoza, Saxenda) and tirzepatide (Mounjaro, Zepbound), compared with SGLT2 inhibitors and with all other reports, in FDA FAERS and Health Canada's Canada Vigilance database? Do differences appear after July 2023, when EMA began its review and the question reached the news?

## Reference results

**EMA's Pharmacovigilance Risk Assessment Committee (PRAC)** opened a review in July 2023 after the Icelandic Medicines Agency reported cases of suicidal thoughts and self-injury with liraglutide and semaglutide. In April 2024 PRAC concluded that the evidence from non-clinical studies, clinical trials and post-marketing surveillance did not support a causal link and that no change to the product information was needed.

**FDA's preliminary evaluation (Drug Safety Communication, 11 January 2024)** found no evidence of a causal link in FAERS reports or trials, while noting it could not rule out a small risk. On 13 January 2026 FDA asked for the suicidal behaviour and ideation warning to be removed from the Saxenda, Wegovy and Zepbound labels, citing a meta-analysis of 91 placebo-controlled trials (107,910 patients) and a Sentinel cohort of 2,243,138 new users that compared GLP-1 receptor agonists with SGLT2 inhibitors and found no increased risk of intentional self-harm.

**A disproportionality study of the WHO database** (Schoretsanitis et al., JAMA Network Open 2024;7(8), doi:10.1001/jamanetworkopen.2024.23385) found a reporting signal for semaglutide and suicidal ideation (ROR 1.45, 95% CI 1.18 to 1.77) against all other drugs, and larger RORs against dapagliflozin, metformin and orlistat.

This project investigates whether FAERS and Canada Vigilance indicate a similar pattern, and whether the signal holds against an active comparator and outside the period of media attention.

## Data

FAERS quarterly ASCII files, 2019 Q1 to the latest published quarter, and the Canada Vigilance extract dated 30 June 2026. Both are the same downloads used by [Safety Signal Explorer](https://github.com/mgoldenitz/safety-signal-explorer); this pipeline reads them from `~/ssx_data/raw` and builds its own database in `~/glp1_data`.

## Method

The pipeline is adapted from Safety Signal Explorer: FAERS de-duplication by latest case version, removal of FDA-deleted cases, primary and secondary suspect drugs only, whole-word drug matching on active ingredient and brand name, and ROR, PRR (Evans criteria) and IC025 from 2 x 2 tables.

**Exposures:** Semaglutide, liraglutide and tirzepatide, each split by the indication on the drug row (type 2 diabetes, weight management, other, unknown; the brand decides when no indication is given), compounded semaglutide and tirzepatide (no FAERS drug names in the first run said "compounded", so this subgroup is empty), and the GLP-1 class (adding dulaglutide, exenatide and lixisenatide).

**Backgrounds:** All other reports; SGLT2 inhibitors (empagliflozin, dapagliflozin, canagliflozin, ertugliflozin, bexagliflozin); and SGLT2 inhibitors given for type 2 diabetes only, since empagliflozin and dapagliflozin are also used for heart failure and kidney disease. SGLT2 inhibitors are the active comparator because they treat the same disease and have no known psychiatric effect.

**Outcomes:** Three groups of MedDRA preferred terms written before any data were loaded (suicidal and self-injurious behaviour, depression, anxiety; listed in `scripts/common.py`), plus each term on its own. MedDRA's Standardised MedDRA Queries need a licence, so the groups are an approximation.

**Notoriety bias:** The psychiatric results are repeated for reports first received before July 2023 and from July 2023 onward, with the background limited to the same period. Reporter type: the FAERS psychiatric results are also repeated within health-professional reports and within consumer reports (added after the first run, when the depression result raised the question).

**Validation, run before any psychiatric result is read:** Label reactions as positive controls (nausea, vomiting, decreased appetite, pancreatitis, gallbladder disease and injection site reactions for GLP-1 drugs; ketoacidosis, genital fungal infection and Fournier's gangrene for SGLT2 inhibitors), comparator checks (nausea should be flagged against SGLT2 inhibitors; ketoacidosis should not), and four negative controls picked from a fixed candidate list by a report-count rule.

## Findings

All figures are reporting odds ratios (ROR) with 95% confidence intervals, from the first full run: FAERS 2019 Q1 to 2026 Q3 (13,324,077 report versions, 11,186,330 cases after de-duplication) and Canada Vigilance reports received from 2019 to 30 June 2026 (567,733). FAERS has 90,020 semaglutide, 12,604 liraglutide, 172,597 tirzepatide and 81,554 SGLT2 inhibitor cases.

**Validation:** All 12 positive controls and both comparator checks behaved as expected; for example, nausea with GLP-1 drugs had an ROR of 4.00 (3.96 to 4.05) against all of FAERS and ketoacidosis with SGLT2 inhibitors 765 (702 to 834). Against SGLT2 inhibitors, three of the four negative controls had RORs of 1.11 to 1.24: none significant, so that background raises the ROR of an unrelated reaction by roughly 10 to 25 percent. The fourth, Sunburn, is discussed under Limitations.

**Semaglutide and suicidality:** Against SGLT2 inhibitors, the suicidal and self-injurious behaviour group does not indicate a signal in reports received before July 2023 (ROR 1.10, 0.86 to 1.40; 101 reports), then suddenly indicates a signal from July 2023 onward (3.16, 2.67 to 3.73; 894 reports). Semaglutide reports in this group rose from 26 in 2023 Q2 to 93 in 2023 Q3, the same quarter EMA's review began. Over the same two periods the SGLT2 inhibitors' ROR for the group against all of FAERS stayed flat (0.39, then 0.34), so the rise belongs to the GLP-1 drugs; FAERS as a whole did not indicate the same pattern, which supports the explanation of stimulated reporting after publicity. The suicidality signal against SGLT2 inhibitors is also present within health-professional reports (3.16, 2.71 to 3.69; 466 reports, all years); this subset was not split by period.

**Ideation and acts:** Suicidal ideation carries the group signal (semaglutide against SGLT2 inhibitors, all years: 6.07, 4.96 to 7.42; 735 reports), while completed suicide does not (0.75, 0.53 to 1.06; 58 reports). Suicide attempt is borderline (1.24, 0.91 to 1.70; 93 reports). Against all of FAERS, semaglutide's group ROR is below 1 (0.91, 0.85 to 0.97). That background includes reports for antidepressants and other psychiatric drugs.

**Tirzepatide:** EMA's review did not cover this; the drug shows no suicidality signal against SGLT2 inhibitors given for diabetes (1.05, 0.86 to 1.29; 614 reports).

**Liraglutide:** Already had a suicidality signal against SGLT2 inhibitors before July 2023 (2.36, 1.82 to 3.05; 83 reports), led by the weight-management subgroup. One possible reason is that the Saxenda label carried a suicidal behaviour and ideation warning, until the FDA asked for its removal in January 2026; in contrast, the diabetes GLP-1 labels has never had such a label. 
 
**Depression and anxiety:** Semaglutide-depression reports are raised against SGLT2 inhibitors even before July 2023 (2.53, 2.10 to 3.03), above the 1.1 to 1.2 range the negative controls give. Most GLP-1 reports come from consumers, while SGLT2 reports more often from physicians, so the analysis was repeated within each reporter type. The depression signal holds in both: 3.19 (2.74 to 3.72; 483 reports) in health-professional reports and 4.14 (3.48 to 4.92; 1,108 reports) in consumer reports. Reporter type does not explain it. Within health-professional reports the weight-management subgroup is higher (3.87, 3.24 to 4.62) than the type 2 diabetes subgroup (2.03, 1.69 to 2.43). The two report populations also differ by sex (60% of semaglutide reports are for women against 39% for SGLT2 inhibitors), which is not adjusted for. The depression signal survives the comparator and the reporter split; this design cannot separate a drug effect from differences between people treated for weight and people treated for diabetes.

**Canada Vigilance:** Semaglutide's suicidality group is raised against all Canadian reports (2.87, 2.24 to 3.69; 64 reports), including before July 2023 (1.75, 1.01 to 3.03; 13 reports). Canada Vigilance has only 2,368 SGLT2 inhibitor reports and 13 of them fall in the suicidality group, so the SGLT2 comparison is too unstable to use for Canada.

These results support EMA (April 2024) and FDA (January 2026) in finding no evidence that semaglutide causes suicidal acts. They differ from the WHO database study's ROR of 1.45 against all drugs, which covered reports to August 2023 and a different background database.

## Running it

In WSL, from the repo folder:

```
~/brainenv/bin/python -m pytest -q tests
bash run_all.sh ~/brainenv/bin/python
```

Steps: `01_download_faers.py` (only quarters not already in `~/ssx_data/raw/faers`), `02_load_faers.py`, `03_deduplicate.py`, `04_signals.py`, `05_validate.py` (stops the run if a positive control fails), `06_canada_vigilance.py`, `07_export.py`. Set `GLP_DATA`, `GLP_FAERS_RAW` or `GLP_CV_RAW` to use other folders.

## Outputs

`outputs/psych_signals.csv` is the main Tableau source; `TABLEAU_STEPS.md` has the dashboard build steps (psychiatric terms and groups, both databases, all backgrounds and subsets). `signals.csv` and `cv_signals.csv` hold every drug-reaction pair with at least 3 reports. Also `validation.csv`, `drugs.csv`, `term_groups.csv`, `reports_by_quarter.csv`, `reporters.csv`, `demographics.csv`, `outcomes.csv`, `cv_reports_by_year.csv`, `pt_soc.csv`, `data_summary.csv`.

## Limitations

Spontaneous reports only indicate a correlation. They cannot measure incidence or show causation, and there is no count of people exposed. Most GLP-1 reports come from consumers (62% of semaglutide reports before July 2023, 80% to 93% of tirzepatide reports), while SGLT2 inhibitor reports come more often from physicians. The weight-management subgroups are compared with a diabetes comparator, so differences between the two patient groups, including their psychiatric history, are confounded in with any drug effect. Media coverage from July 2023 can raise reporting by itself. No FAERS drug name in this run said "compounded", so reports for compounded semaglutide or tirzepatide cannot be separated. The term groups and indication rules approximate MedDRA.

One of the four negative controls, Sunburn, was flagged for GLP-1 drugs (155 reports, ROR 1.70, 95% CI 1.44 to 1.99). The terms most often reported with it are sensitive skin (22 reports), pain of skin (15), allodynia (12), paraesthesia (11) and hyperaesthesia (6), so these look like reports of altered skin sensation coded as Sunburn. New Zealand's Medsafe (Prescriber Update, March 2026) lists altered skin sensations, including dysaesthesia, for semaglutide (2.1% of Wegovy patients in trials against 1.2% on placebo) and tirzepatide. The control was kept, since it was chosen by a fixed rule before results were read.
