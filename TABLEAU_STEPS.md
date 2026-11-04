# Tableau dashboard: build steps

Tableau Public (free desktop app) or Tableau Desktop. Four sheets and one dashboard, built from three files in `outputs/`: `psych_signals.csv`, `reports_by_quarter.csv` and `validation.csv`. Each file is its own data source; none of them join.

In `psych_signals.csv` the column `period` holds the subset of reports: All years, Before July 2023, July 2023 onward, Health professional reports or Consumer reports. Rename it to `Subset` in Tableau (right-click > Rename) so the sheets read clearly.

## 1. Connect the data

1. Connect > Text file > `outputs/psych_signals.csv`.
2. Data > New Data Source > Text file > `outputs/reports_by_quarter.csv`.
3. Data > New Data Source > Text file > `outputs/validation.csv`.

In `psych_signals.csv`, check that `a`, `ror`, `ror_lo` and `ror_hi` are measures and `signal_ror` and `is_group` are Boolean.

Add a data source filter (Data > Edit Data Source Filters) on `psych_signals.csv`: `a` at least 3. Rows with fewer than 3 reports cannot flag a signal, and some have no ROR at all.

## 2. Sheet "Before and after" (psych_signals.csv)

A forest plot: one row per drug and term group, a dot for the ROR and a line for its 95% confidence interval, with before and after July 2023 side by side.

1. Filters: `is_group` = True; `Subset` in Before July 2023, July 2023 onward; `exposure` in semaglutide, liraglutide, tirzepatide, GLP-1 RA (any).
2. Show `database` and `background` as single-value dropdown filters. Default to FAERS and SGLT2 inhibitors.
3. Rows: `term`, then `exposure`.
4. Columns: `AVG(ror_lo)`. Mark type: Gantt Bar. Calculated field `CI width` = `AVG([ror_hi]) - AVG([ror_lo])`, on Size. This draws the confidence interval.
5. Drag `AVG(ror)` onto Columns next to it, make it a dual axis, Synchronize Axis, and set its mark type to Circle.
6. Color (both mark cards): `Subset`. Grey for Before July 2023, a strong colour for July 2023 onward.
7. Right-click the axis > Edit Axis > Logarithmic. Add a reference line at constant 1 (Analytics pane > Reference Line), dashed, labelled "No difference".
8. Tooltip: `a` (reports), `ror`, `ror_lo`, `ror_hi`.
9. Title: "Reporting odds ratio, before and after EMA's review (July 2023)".

## 3. Sheet "Reports per quarter" (reports_by_quarter.csv)

1. Calculated field `Quarter start` = `MAKEDATE(INT(LEFT([quarter], 4)), (INT(RIGHT([quarter], 1)) - 1) * 3 + 1, 1)`.
2. Filters: `year` at least 2019; `measure` = Suicidal and self-injurious behaviour; `exposure` in semaglutide, liraglutide, tirzepatide.
3. Columns: `Quarter start` as a continuous quarter (right-click > Quarter, the second, green option). Rows: `SUM(reports)`. Mark type: Line. Color: `exposure`.
4. Analytics pane > Reference Line on the date axis, constant 1 July 2023, label "EMA review opened".
5. Show `measure` as a dropdown filter so the viewer can switch to Depression or Anxiety.
6. Title: "Reports by quarter first received".

## 4. Sheet "Who reported" (psych_signals.csv)

1. Filters: `is_group` = True; `database` = FAERS; `background` = SGLT2 inhibitors; `Subset` in Health professional reports, Consumer reports; `exposure` in semaglutide, liraglutide, tirzepatide.
2. Build the same Gantt-plus-circle forest plot as sheet 2, with Color on `Subset`.
3. Title: "Reporting odds ratio against SGLT2 inhibitors, by reporter type".

## 5. Sheet "Validation" (validation.csv)

1. Rows: `kind`, `exposure`, `reaction`. Mark type: Text.
2. Text: `reports`, `ror` (2 decimals), `ror_lo` (2 decimals), `passed`.
3. Color: `passed` (True green, False orange). Sunburn will show as False; the dashboard note below explains it.
4. Title: "Controls checked before any psychiatric result".

## 6. Dashboard

1. Size: Automatic, or 1400 x 900.
2. "Before and after" across the top. "Reports per quarter" and "Who reported" side by side below it. "Validation" on a second dashboard tab, or collapsed at the bottom.
3. Dashboard > Actions > Add Action > Filter: source "Before and after", target "Reports per quarter", field `exposure` mapped to `exposure`, run on Select.
4. A text box with the data and limits: "FDA FAERS 2019 Q1 to 2026 Q3 (11,186,330 cases) and Health Canada Canada Vigilance to 30 June 2026. Spontaneous reports show association only; they cannot measure incidence or show causation. Comparator: SGLT2 inhibitors. Sunburn was flagged as a negative control because altered skin sensations were coded as Sunburn. Code: github.com/mgoldenitz/glp1-psychiatric-signals."

## 7. Publish

Tableau Public: File > Save to Tableau Public. FAERS and Canada Vigilance are public data, so publishing them is allowed. Add the link to the top of `README.md`, and export an image of the dashboard to `images/tableau_dashboard.png`.
