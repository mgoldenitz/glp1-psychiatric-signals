# Running the GLP-1 pipeline in WSL

The pipeline reads the Safety Signal Explorer downloads in `~/ssx_data/raw/faers` and `~/ssx_data/raw/canada_vigilance`. Step 01 downloads any FAERS quarter that is not there yet; the first run on 3 November 2026 added 2026 Q3, for 31 quarters in all. The Canada Vigilance extract is downloaded by hand from Health Canada.

1. Get the code: `cd ~ && git clone https://github.com/mgoldenitz/glp1-psychiatric-signals.git && cd glp1-psychiatric-signals`. Keep it in WSL, outside OneDrive, where SQLite builds fail.

2. Run the tests (about 2 seconds): `~/brainenv/bin/python -m pytest -q tests`. Expect `14 passed`.

3. Run the pipeline: `mkdir -p ~/glp1_data && bash run_all.sh ~/brainenv/bin/python 2>&1 | tee ~/glp1_data/run_log.txt`. Most of the time goes to step 02, which loads every quarter into `~/glp1_data/glp1.sqlite`.

4. If the run stops at step 05, a positive control failed. Read the validation table in the log before anything else.

5. Check the sizes with `ls -lh outputs`. GitHub refuses files over 100 MB; on the first run `signals.csv` was 32 MB.

6. Commit the outputs: `git add outputs && git commit -m "Update outputs" && git push`.

To rerun only the signal steps after a code change (about 10 minutes, no reload): `git pull && for s in 04_signals 05_validate 06_canada_vigilance 07_export; do ~/brainenv/bin/python scripts/$s.py || break; done 2>&1 | tee ~/glp1_data/rerun_log.txt`.

If `~/ssx_data` was moved or deleted, set the folders first: `export GLP_FAERS_RAW=/path/to/faers/zips GLP_CV_RAW=/path/to/canada_vigilance`.
