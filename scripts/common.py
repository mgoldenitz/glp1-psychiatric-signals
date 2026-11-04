"""Shared settings and helpers for the GLP-1 psychiatric signals pipeline.

The pipeline is adapted from Safety Signal Explorer (mgoldenitz/safety-signal-explorer).
It reads the same FAERS quarterly zips and Canada Vigilance extract, so nothing
has to be downloaded twice.

Locations (all outside OneDrive, where SQLite builds fail):
    GLP_DATA       database and outputs of this project (default ~/glp1_data)
    GLP_FAERS_RAW  folder of faers_ascii_*.zip files (default ~/ssx_data/raw/faers
                   if it exists, otherwise $GLP_DATA/raw/faers)
    GLP_CV_RAW     unzipped Canada Vigilance extract (default
                   ~/ssx_data/raw/canada_vigilance if it exists)
"""

import os
import re
import sqlite3
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("GLP_DATA", Path.home() / "glp1_data"))
DB_PATH = DATA / "glp1.sqlite"
OUTPUTS = REPO / "outputs"


def _default_raw(env, ssx_sub, own_sub):
    if os.environ.get(env):
        return Path(os.environ[env])
    ssx = Path.home() / "ssx_data" / "raw" / ssx_sub
    return ssx if ssx.exists() else DATA / "raw" / own_sub


RAW_FAERS = _default_raw("GLP_FAERS_RAW", "faers", "faers")
RAW_CV = _default_raw("GLP_CV_RAW", "canada_vigilance", "canada_vigilance")

# 2019 Q1 matches Safety Signal Explorer, so the same downloads are reused.
# Semaglutide (Ozempic, US approval December 2017) and liraglutide (2010) are
# on the market for the whole period; tirzepatide from May 2022.
START_QUARTER = "2019Q1"

# The Icelandic Medicines Agency raised suicidal thoughts with semaglutide and
# liraglutide and EMA's PRAC opened a review in July 2023. Media coverage
# followed, which can raise reporting of these terms on its own (notoriety
# bias). Reports are split by the date FDA or Health Canada first received them.
PERIOD_CUTOFF = "2023-07-01"
PERIODS = ["All years", "Before July 2023", "July 2023 onward"]

SUSPECT_ROLES = ("PS", "SS")

# Drug groups. Each generic name matches on whole words in the active
# ingredient or the verbatim drug name. Brand names catch reports with no
# active ingredient, including combination products (Xultophy is insulin
# degludec plus liraglutide; Synjardy is empagliflozin plus metformin).
DRUGS = {
    # generic: (group, [names to match])
    "semaglutide": ("GLP-1 RA", ["SEMAGLUTIDE", "OZEMPIC", "WEGOVY", "RYBELSUS"]),
    "liraglutide": ("GLP-1 RA", ["LIRAGLUTIDE", "VICTOZA", "SAXENDA", "XULTOPHY"]),
    "tirzepatide": ("GLP-1 RA", ["TIRZEPATIDE", "MOUNJARO", "ZEPBOUND"]),
    "dulaglutide": ("Other GLP-1 RA", ["DULAGLUTIDE", "TRULICITY"]),
    "exenatide": ("Other GLP-1 RA", ["EXENATIDE", "BYETTA", "BYDUREON"]),
    "lixisenatide": ("Other GLP-1 RA", ["LIXISENATIDE", "ADLYXIN", "LYXUMIA", "SOLIQUA", "SULIQUA"]),
    "empagliflozin": ("SGLT2 inhibitor", ["EMPAGLIFLOZIN", "JARDIANCE", "SYNJARDY", "GLYXAMBI", "TRIJARDY"]),
    "dapagliflozin": ("SGLT2 inhibitor", ["DAPAGLIFLOZIN", "FARXIGA", "FORXIGA", "XIGDUO", "QTERN"]),
    "canagliflozin": ("SGLT2 inhibitor", ["CANAGLIFLOZIN", "INVOKANA", "INVOKAMET"]),
    "ertugliflozin": ("SGLT2 inhibitor", ["ERTUGLIFLOZIN", "STEGLATRO", "SEGLUROMET", "STEGLUJAN"]),
    "bexagliflozin": ("SGLT2 inhibitor", ["BEXAGLIFLOZIN", "BRENZAVVY"]),
}
GLP1 = [d for d, (g, _) in DRUGS.items() if "GLP-1" in g]
MAIN_GLP1 = [d for d, (g, _) in DRUGS.items() if g == "GLP-1 RA"]
COMPARATORS = [d for d, (g, _) in DRUGS.items() if g == "SGLT2 inhibitor"]
CLASS_EXPOSURE = "GLP-1 RA (any)"
SGLT2_CLASS_EXPOSURE = "SGLT2 inhibitor (any)"

_PATTERNS = {
    drug: re.compile(r"\b(" + "|".join(names) + r")\b") for drug, (_, names) in DRUGS.items()
}


def match_drugs(text):
    """Return the set of generic names found in a drug name or ingredient string."""
    if not isinstance(text, str) or not text:
        return set()
    text = text.upper()
    return {drug for drug, pat in _PATTERNS.items() if pat.search(text)}


def base_drug(exposure):
    """'semaglutide: weight management' -> 'semaglutide'. The SGLT2 class counts as a comparator."""
    e = str(exposure)
    return COMPARATORS[0] if e == SGLT2_CLASS_EXPOSURE else e.split(":")[0]


# Indication groups. GLP-1 drugs are used for type 2 diabetes and for weight
# management, and people treated for obesity have higher rates of depression
# than people treated for diabetes, so the GLP-1 reports are split by the
# indication given on the drug row. When no indication is given, the brand
# decides (Wegovy, Saxenda and Zepbound are the weight-management brands).
# SGLT2 inhibitors are also split, because empagliflozin and dapagliflozin are
# approved for heart failure and kidney disease as well as diabetes.
INDICATION_RULES = [
    ("unknown", ["PRODUCT USED FOR UNKNOWN INDICATION"]),
    ("weight management", ["OBES", "OVERWEIGHT", "WEIGHT", "BODY MASS INDEX", "DIET"]),
    ("type 2 diabetes", ["DIABET", "GLYCAEMI", "GLYCEMI", "BLOOD GLUCOSE", "GLYCOSYLATED",
                         "HAEMOGLOBIN A1C", "HEMOGLOBIN A1C", "HYPERGLYC", "INSULIN RESISTANCE"]),
    ("heart failure or kidney disease", ["HEART FAILURE", "CARDIAC FAILURE", "KIDNEY", "RENAL",
                                         "NEPHROPATHY", "EJECTION FRACTION"]),
]
WEIGHT_BRANDS = re.compile(r"\b(WEGOVY|SAXENDA|ZEPBOUND)\b")
DIABETES_BRANDS = re.compile(r"\b(OZEMPIC|RYBELSUS|VICTOZA|XULTOPHY|MOUNJARO|TRULICITY|BYETTA|"
                             r"BYDUREON|ADLYXIN|LYXUMIA|SOLIQUA|SULIQUA)\b")


def indication_group(indi_pt, drugname=None):
    """Indication group for one drug row: from the indication term, else from the brand."""
    if isinstance(indi_pt, str) and indi_pt.strip():
        t = indi_pt.upper()
        for label, keys in INDICATION_RULES:
            if any(k in t for k in keys):
                if label != "unknown":
                    return label
                break
        else:
            return "other"
    name = str(drugname or "").upper()
    if WEIGHT_BRANDS.search(name):
        return "weight management"
    if DIABETES_BRANDS.search(name):
        return "type 2 diabetes"
    return "unknown"


def is_compounded(drugname):
    """Compounded semaglutide and tirzepatide were sold widely during the 2022 to 2025 shortages."""
    return isinstance(drugname, str) and "COMPOUND" in drugname.upper()


# Psychiatric term groups. MedDRA's Standardised MedDRA Queries need a
# licence, so these groups are lists of MedDRA preferred terms as they appear
# in FAERS and Canada Vigilance, written before any result was looked at.
# A report counts once per group however many of its terms match.
TERM_GROUPS = {
    "Suicidal and self-injurious behaviour": [
        "Suicidal ideation", "Suicide attempt", "Completed suicide", "Suicidal behaviour",
        "Intentional self-injury", "Self-injurious ideation", "Depression suicidal",
        "Suicide threat", "Intentional overdose", "Poisoning deliberate", "Self-destructive behaviour",
    ],
    "Depression": [
        "Depression", "Depressed mood", "Major depression", "Depressive symptom",
        "Persistent depressive disorder", "Anhedonia", "Feeling of despair", "Dysthymic disorder",
    ],
    "Anxiety": [
        "Anxiety", "Anxiety disorder", "Generalised anxiety disorder", "Panic attack",
        "Panic disorder", "Nervousness", "Fear", "Tension",
    ],
}
GROUP_PREFIX = "Group: "


def target_terms():
    """Upper-case keys of every term in a group, plus the group names."""
    keys = {t.upper() for terms in TERM_GROUPS.values() for t in terms}
    return keys | {(GROUP_PREFIX + g).upper() for g in TERM_GROUPS}


def quarters(start, end):
    """Yield quarter labels like '2019Q1' from start to end inclusive."""
    y, q = int(start[:4]), int(start[-1])
    ey, eq = int(end[:4]), int(end[-1])
    while (y, q) <= (ey, eq):
        yield f"{y}Q{q}"
        y, q = (y + 1, 1) if q == 4 else (y, q + 1)


def connect(path=None):
    path = Path(path or DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    return con


# Terms that describe a product, device, use or administrative event rather
# than a clinical reaction (same rules as Safety Signal Explorer).
_NON_CLINICAL = [
    ("Lack of effect", ["DRUG INEFFECTIVE", "THERAPEUTIC PRODUCT EFFECT", "THERAPEUTIC RESPONSE",
                        "TREATMENT FAILURE", "LACK OF EFFICACY", "NON-RESPONDER",
                        "EFFECT LESS THAN EXPECTED", "EFFECT INCOMPLETE", "LACK OF CONCOMITANT"]),
    ("Product, device or use", ["DEVICE", "PRODUCT", "MEDICATION ERROR", "OFF LABEL",
                                "WRONG ", "INCORRECT ", "UNDERDOSE", "NONCOMPLIANCE",
                                "NON-COMPLIANCE", "INTERCEPTED", "EXPOSURE ", "EXPOSURE VIA",
                                "INAPPROPRIATE SCHEDULE", "EXTRA DOSE", "DOSE OMISSION",
                                "PRESCRIBED", "DRUG DOSE", "DRUG ADMINISTRATION",
                                "CIRCUMSTANCE OR INFORMATION", "INSURANCE", "LABELLED DRUG",
                                "UNAPPROVED INDICATION", "DELIVERY SYSTEM", "MONITORING PROCEDURE",
                                "ISSUE", "TITRATION ERROR", "WITHOUT A PRESCRIPTION", " USER "]),
    ("Procedure or administrative", ["HOSPITALISATION", "SURGERY", "OPERATION",
                                     "PHYSICAL EXAMINATION", "NO ADVERSE EVENT",
                                     "ADVERSE EVENT", "ADVERSE DRUG REACTION", "THERAPY CESSATION",
                                     "THERAPY INTERRUPTED", "THERAPY CHANGE", "TREATMENT DELAYED",
                                     "DEATH", "PROCEDURE ", "THERAPY ", "CHEMOTHERAPY", "RADIOTHERAPY"]),
]
_CLINICAL_EXCEPTIONS = ["OVERDOSE", "SUDDEN DEATH", "SUDDEN CARDIAC DEATH", "BRAIN DEATH"]


def term_category(pt):
    """Term group, Clinical, or one of the non-clinical groups above."""
    if str(pt).startswith(GROUP_PREFIX):
        return "Term group"
    t = str(pt).upper() + " "
    if any(x in t for x in _CLINICAL_EXCEPTIONS):
        return "Clinical"
    for label, keys in _NON_CLINICAL:
        if any(k in t for k in keys):
            return label
    return "Clinical"


def stats(df):
    """Add PRR, ROR, IC and signal flags to a frame with columns a, b, c, d."""
    a, b, c, d = (df[k].astype(float) for k in "abcd")
    n = a + b + c + d
    with np.errstate(divide="ignore", invalid="ignore"):
        prr = (a / (a + b)) / (c / (c + d))
        se_prr = np.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
        ror = (a * d) / (b * c)
        se_ror = np.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
        chi2 = n * (np.abs(a * d - b * c) - n / 2).clip(lower=0) ** 2 / (
            (a + b) * (c + d) * (a + c) * (b + d))
        expected = (a + b) * (a + c) / n
        ic = np.log2((a + 0.5) / (expected + 0.5))
        ic025 = ic - 3.3 * (a + 0.5) ** -0.5 - 2 * (a + 0.5) ** -1.5
    out = df.copy()
    out["expected"] = expected
    out["prr"] = prr
    out["prr_lo"] = np.exp(np.log(prr) - 1.96 * se_prr)
    out["prr_hi"] = np.exp(np.log(prr) + 1.96 * se_prr)
    out["chi2"] = chi2
    out["ror"] = ror
    out["ror_lo"] = np.exp(np.log(ror) - 1.96 * se_ror)
    out["ror_hi"] = np.exp(np.log(ror) + 1.96 * se_ror)
    out["ic"] = ic
    out["ic025"] = ic025
    out["signal_evans"] = (a >= 3) & (prr >= 2) & (chi2 >= 4)
    out["signal_ror"] = (a >= 3) & (out["ror_lo"] > 1)
    out["signal_ic"] = ic025 > 0
    return out.replace([np.inf, -np.inf], np.nan)
