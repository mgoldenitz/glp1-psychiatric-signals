# Running the GLP-1 pipeline in WSL

These steps assume the Safety Signal Explorer downloads are still in `~/ssx_data/raw/faers` (30 zips, 2019 Q1 to 2026 Q2) and `~/ssx_data/raw/canada_vigilance`. Nothing else needs downloading by hand. If FDA has posted 2026 Q3 since October, step 3 downloads it.

1. Get the code. Once the GitHub repo exists: `cd ~ && git clone https://github.com/mgoldenitz/glp1-psychiatric-signals.git && cd glp1-psychiatric-signals`. Keep it in WSL, not in OneDrive.

2. Run the tests (about 2 seconds): `~/brainenv/bin/python -m pytest -q tests`. Expect `14 passed`.

3. Run the pipeline: `mkdir -p ~/glp1_data && bash run_all.sh ~/brainenv/bin/python 2>&1 | tee ~/glp1_data/run_log.txt`. Expect 40 to 60 minutes, most of it in step 02 (loading 30 quarters). The database goes to `~/glp1_data/glp1.sqlite`, about the same size as `~/ssx_data/ssx.sqlite`.

4. If the run stops at step 05, a positive control failed. Do not read anything else; send Claude the validation table from the log.

5. When it finishes, send Claude `~/glp1_data/run_log.txt`, or paste three parts of it: the exposure counts printed by step 03, the validation table from step 05, and the term-group table printed by step 07.

6. Check that `outputs/psych_signals.csv` exists and that `outputs/signals.csv` is under 100 MB (`ls -lh outputs`). GitHub refuses files over 100 MB.

If `~/ssx_data` was moved or deleted, set the folders first: `export GLP_FAERS_RAW=/path/to/faers/zips GLP_CV_RAW=/path/to/canada_vigilance`.
