"""
ETL pipeline for GES (Graduate Employment Survey) data.
Handles loading, cleaning, normalising degree names, categorising degrees,
and merging new uploads.
"""

import pandas as pd
import os
import re


MASTER_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "wrangledGES.csv")

COLUMNS = [
    "year", "university", "school", "degree",
    "employment_rate_overall", "employment_rate_ft_perm",
    "basic_monthly_mean", "basic_monthly_median",
    "gross_monthly_mean", "gross_monthly_median",
    "gross_mthly_25_percentile", "gross_mthly_75_percentile",
]

METRIC_LABELS = {
    "employment_rate_overall": "Employment Rate (Overall)",
    "employment_rate_ft_perm": "Employment Rate (Full-Time Permanent)",
    "basic_monthly_mean": "Basic Monthly Mean ($)",
    "basic_monthly_median": "Basic Monthly Median ($)",
    "gross_monthly_mean": "Gross Monthly Mean ($)",
    "gross_monthly_median": "Gross Monthly Median ($)",
    "gross_mthly_25_percentile": "Gross Monthly 25th Percentile ($)",
    "gross_mthly_75_percentile": "Gross Monthly 75th Percentile ($)",
}

RATE_METRICS = {"employment_rate_overall", "employment_rate_ft_perm"}


# ─────────────────────────────────────────────
# Canonical degree normalisation
# ─────────────────────────────────────────────
# Maps a regex pattern (matched against lowercased raw degree) → (canonical name, category).
# Order matters: more specific patterns first. Having the category live right next
# to the canonical name guarantees there is exactly one category per degree —
# no separate keyword re-scan that can misfire (e.g. "Business Analytics" being
# caught by a loose "business" keyword, or "Biomedical Engineering" being caught
# by a loose "biomedical" keyword meant for healthcare degrees).
_CANONICAL_RULES: list[tuple[str, str, str]] = [
    # pattern, canonical name, category

    # ── Double degrees ────────────────────────
    (r"double degree.*accountancy.*business",          "Double Degree (Accountancy & Business)", "Business"),
    (r"double degree.*business.*computer",              "Double Degree (Business & Computer Science)", "Business"),
    (r"double degree.*engineering.*economics",          "Double Degree (Engineering & Economics)", "Engineering"),
    (r"double degree.*engineering.*computer science",   "Double Degree (Engineering & Computer Science)", "Engineering"),
    (r"double degree.*biomedical.*chinese medicine",    "Double Degree (Biomedical Sciences & Chinese Medicine)", "Healthcare"),

    # ── Computing & Law ───────────────────────
    (r"computing.*law",                                 "Computing & Law", "Law"),

    # ── Architecture & Design ─────────────────
    (r"architecture",                                   "Architecture", "Architecture & Design"),
    (r"interior design",                                "Interior Design", "Architecture & Design"),
    (r"industrial design",                              "Industrial Design", "Architecture & Design"),
    (r"game design|user experience.*game|game.*user experience",
                                                        "Game Design", "Architecture & Design"),
    (r"art.*design.*media|art,? design",                "Art, Design & Media", "Architecture & Design"),
    (r"^bachelor of fine arts",                         "Fine Arts", "Architecture & Design"),

    # ── Engineering ────────────────────────────
    (r"aerospace|aeronautical|aircraft|aerospace systems", "Aerospace Engineering", "Engineering"),
    (r"bioengineering|biomedical engineering",          "Biomedical Engineering", "Engineering"),
    (r"chemical.*biomolecular|chemical engineering",    "Chemical & Biomolecular Engineering", "Engineering"),
    (r"civil engineering",                              "Civil Engineering", "Engineering"),
    (r"computer engineering",                           "Computer Engineering", "Engineering"),
    (r"electrical.*electronic|electrical power|electronics and data",
                                                        "Electrical & Electronic Engineering", "Engineering"),
    (r"electrical engineering.*information technology|electrical engineering.*ict",
                                                        "Electrical Engineering & IT", "Engineering"),
    (r"electrical engineering",                         "Electrical Engineering", "Engineering"),
    (r"sustainable infrastructure",                     "Sustainable Infrastructure Engineering", "Engineering"),
    (r"environmental engineering",                      "Environmental Engineering", "Engineering"),
    (r"industrial.*systems engineering",                "Industrial & Systems Engineering", "Engineering"),
    (r"information engineering.*media",                 "Information Engineering & Media", "Engineering"),
    (r"materials engineering|materials science",        "Materials Engineering", "Engineering"),
    (r"marine engineering|offshore engineering",        "Marine & Offshore Engineering", "Engineering"),
    (r"mechanical design.*manufacturing|mechanical design engineering",
                                                        "Mechanical Engineering (Design & Manufacturing)", "Engineering"),
    (r"mechanical engineering",                         "Mechanical Engineering", "Engineering"),
    (r"mechatronics",                                   "Mechatronics Engineering", "Engineering"),
    (r"robotics systems",                                "Robotics Engineering", "Engineering"),
    (r"pharmaceutical engineering",                     "Pharmaceutical Engineering", "Engineering"),
    (r"intelligent transportation systems engineering", "Intelligent Transportation Systems Engineering", "Engineering"),
    (r"engineering product development",                "Engineering Product Development", "Engineering"),
    (r"engineering science",                            "Engineering Science", "Engineering"),
    (r"engineering systems and design",                 "Engineering Systems & Design", "Engineering"),
    (r"systems engineering.*electromechanical|^systems engineering",
                                                        "Systems Engineering", "Engineering"),
    (r"software engineering",                           "Software Engineering", "Technology"),
    (r"information systems technology and design",      "Information Systems Technology & Design", "Technology"),
    (r"building services",                               "Building Services Engineering", "Engineering"),

    # ── Technology / Computing ────────────────
    (r"computer science.*game design|computer science.*interactive media|computer science.*real.time",
                                                        "Computer Science (Specialisation)", "Technology"),
    (r"computer science.*design",                       "Computer Science & Design", "Technology"),
    (r"computer science",                               "Computer Science", "Technology"),
    (r"computing science",                              "Computer Science", "Technology"),
    (r"data science",                                   "Data Science", "Technology"),
    (r"applied artificial intelligence",                "Applied Artificial Intelligence", "Technology"),
    (r"business analytics",                             "Business Analytics", "Technology"),
    (r"information systems management",                 "Information Systems Management", "Technology"),
    (r"information systems",                            "Information Systems", "Technology"),
    (r"information security",                           "Information Security", "Technology"),
    (r"electronic commerce",                             "Electronic Commerce", "Technology"),
    (r"communications and media.*computing|computing.*communications",
                                                        "Computing (Communications & Media)", "Technology"),
    (r"business and computing|business.*computing",     "Business & Computing", "Technology"),

    # ── Business ───────────────────────────────
    # Only catch genuine combined Accountancy-and-Business degrees (joined by
    # "and"/"&"). Previously used a "business.*accountancy(?! \()" lookahead
    # that was meant to exclude parenthetical specialisations like "Business
    # Administration (Accountancy)" but had the exclusion backwards, so it
    # incorrectly lumped that single-accountancy degree into this combined
    # bucket. Matching only the explicit "and"/"&" join avoids that.
    (r"accountancy\s*(and|&)\s*business|business\s*(and|&)\s*accountancy",
                                                        "Accountancy & Business", "Business"),
    (r"accountancy",                                    "Accountancy", "Business"),
    (r"business administration.*food|food business management",
                                                        "Business Administration (Food Business)", "Business"),
    (r"business administration|business management",    "Business", "Business"),
    (r"human resource management",                      "Human Resource Management", "Business"),
    (r"^business(\s|$)|^bachelor of business|hospitality business",
                                                        "Business", "Business"),
    (r"economics.*mathematics|mathematics.*economics",  "Mathematics & Economics", "Arts & Social Sciences"),
    (r"economics",                                      "Economics", "Arts & Social Sciences"),
    (r"finance",                                        "Finance", "Business"),
    (r"marketing",                                      "Marketing", "Business"),
    (r"real estate",                                    "Real Estate", "Business"),
    (r"hospitality management",                         "Hospitality Management", "Business"),
    (r"supply chain",                                   "Supply Chain Management", "Business"),
    (r"culinary arts management",                       "Culinary Arts Management", "Business"),

    # ── Law ─────────────────────────────────────
    (r"^law\b|^bachelor of laws|llb|l\.l\.b",           "Law", "Law"),

    # ── Healthcare ───────────────────────────────
    (r"dental surgery",                                 "Dental Surgery", "Healthcare"),
    (r"medicine",                                       "Medicine", "Healthcare"),
    (r"nursing",                                        "Nursing", "Healthcare"),
    (r"physiotherapy",                                  "Physiotherapy", "Healthcare"),
    (r"occupational therapy",                           "Occupational Therapy", "Healthcare"),
    (r"diagnostic radiography",                         "Diagnostic Radiography", "Healthcare"),
    (r"radiation therapy",                              "Radiation Therapy", "Healthcare"),
    (r"chinese medicine",                               "Chinese Medicine", "Healthcare"),
    (r"biomedical sciences.*chinese medicine|chinese medicine.*biomedical",
                                                        "Biomedical Sciences & Chinese Medicine", "Healthcare"),
    (r"computational biology",                          "Computational Biology", "Healthcare"),
    (r"biological.*biomedical|biomedical.*biological",  "Biological & Biomedical Sciences", "Healthcare"),
    (r"biological sciences.*psychology|psychology.*biological",
                                                        "Biological Sciences & Psychology", "Healthcare"),
    (r"biological sciences",                            "Biological Sciences", "Science"),
    (r"speech.*language|language.*speech",              "Speech & Language Therapy", "Healthcare"),
    (r"dietetics.*nutrition|nutrition.*dietetics|food.*human nutrition|human nutrition",
                                                        "Dietetics & Nutrition", "Healthcare"),
    (r"optometry",                                      "Optometry", "Healthcare"),

    # ── Science ───────────────────────────────────
    (r"pharmacy",                                       "Pharmacy", "Science"),
    (r"biomedical sciences|biomedical science",         "Biomedical Sciences", "Science"),
    (r"chemistry.*biological chemistry|biological chemistry",
                                                        "Chemistry & Biological Chemistry", "Science"),
    (r"chemistry",                                      "Chemistry", "Science"),
    (r"physics.*applied physics|applied physics.*physics",
                                                        "Physics & Applied Physics", "Science"),
    (r"physics.*mathematical sciences",                 "Physics & Mathematical Sciences", "Science"),
    (r"physics",                                        "Physics", "Science"),
    (r"mathematical science",                           "Mathematical Sciences", "Science"),
    (r"mathematics",                                    "Mathematics", "Science"),
    (r"statistics",                                     "Statistics", "Science"),
    (r"life science",                                   "Life Sciences", "Science"),
    (r"environmental earth",                            "Environmental Earth Systems Science", "Science"),
    (r"environmental studies",                          "Environmental Studies", "Science"),
    (r"sport science|sports science",                   "Sports Science & Management", "Science"),
    (r"pharmaceutical science",                         "Pharmaceutical Science", "Science"),
    (r"maritime studies",                               "Maritime Studies", "Science"),
    (r"food technology",                                "Food Technology", "Science"),
    (r"applied science",                                "Applied Science", "Science"),
    (r"air transport management",                       "Air Transport Management", "Science"),
    (r"land$",                                          "Land Economy", "Science"),

    # ── Arts & Social Sciences ─────────────────────
    (r"communication studies|communication design|digital communications",
                                                        "Communication Studies", "Arts & Social Sciences"),
    (r"public policy",                                  "Public Policy & Global Affairs", "Arts & Social Sciences"),
    (r"public safety.*security",                        "Public Safety & Security", "Arts & Social Sciences"),
    (r"social work",                                    "Social Work", "Arts & Social Sciences"),
    (r"social sciences",                                "Social Sciences", "Arts & Social Sciences"),
    (r"psychology",                                     "Psychology", "Arts & Social Sciences"),
    (r"sociology",                                      "Sociology", "Arts & Social Sciences"),
    (r"linguistics",                                    "Linguistics & Multilingual Studies", "Arts & Social Sciences"),
    (r"^english$|^english language",                    "English", "Arts & Social Sciences"),
    (r"^chinese$|chinese language",                     "Chinese", "Arts & Social Sciences"),
    (r"history",                                        "History", "Arts & Social Sciences"),
    (r"philosophy",                                     "Philosophy", "Arts & Social Sciences"),
    (r"geography",                                      "Geography", "Arts & Social Sciences"),
    (r"criminology",                                    "Criminology & Security", "Arts & Social Sciences"),
    (r"project.*facilities management",                 "Project & Facilities Management", "Arts & Social Sciences"),
    (r"music",                                          "Music", "Arts & Social Sciences"),
    (r"^bachelor of arts",                               "Arts (General)", "Arts & Social Sciences"),
    (r"^bachelor of science(\s*\(hons?\.?(ours)?\))?$|^bachelor of science with honours$",
                                                        "Science (General)", "Science"),

    (r"inter-?disciplinary double",                     "Interdisciplinary Double Major", "Other"),

    # ── Education ──────────────────────────────────
    (r"early childhood education",                      "Early Childhood Education", "Education"),
    (r"arts.*education|education.*arts",                "Arts (with Education)", "Education"),
    (r"science.*education|education.*science",          "Science (with Education)", "Education"),
    (r"education",                                      "Education", "Education"),
]

# Compile once
_COMPILED_RULES = [(re.compile(p, re.IGNORECASE), name, cat) for p, name, cat in _CANONICAL_RULES]

# Build the canonical-name → category lookup (used by filter_by_category / get_categories)
DEGREE_CATEGORY: dict[str, str] = {name: cat for _, name, cat in _CANONICAL_RULES}

_FALLBACK_CATEGORY = "Other"


def canonicalise_degree(raw: str) -> str:
    """
    Map a raw degree string to a short canonical name.
    Falls back to a cleaned title-case version if no rule matches.
    """
    canon, _ = canonicalise_degree_with_category(raw)
    return canon


def canonicalise_degree_with_category(raw: str) -> tuple[str, str]:
    """
    Map a raw degree string to (canonical name, category) in one pass,
    guaranteeing every degree has exactly one category.

    Idempotent: if `raw` is already an exact canonical name (e.g. because the
    master CSV was previously cleaned and saved), it is returned unchanged
    with its known category, rather than being re-processed and potentially
    falling through to a different/fallback result.
    """
    if not isinstance(raw, str) or not raw.strip():
        return raw, _FALLBACK_CATEGORY

    raw_stripped = raw.strip()
    if raw_stripped in DEGREE_CATEGORY:
        return raw_stripped, DEGREE_CATEGORY[raw_stripped]

    # Strip footnote markers (^, #, digits at end) and 'cum laude' variants
    cleaned = re.sub(r"[\^#\d]+$", "", raw).strip()
    cleaned = re.sub(r"[\s\-]*(cum laude.*)", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    lowered = cleaned.lower()

    for pattern, canonical, category in _COMPILED_RULES:
        if pattern.search(lowered):
            return canonical, category

    # Fallback: strip degree prefix and title-case the specialisation.
    # Ignore "(Hons)" / "(Honours)" as a fake specialisation — if that's all
    # that's in parentheses, fall through to title-casing the base degree name.
    stripped_hons = re.sub(r"\(\s*hons?\.?(ours)?\s*\)\s*$", "", cleaned, flags=re.IGNORECASE).strip()
    m = re.search(
        r"bachelor of (?:science|arts|engineering|computing|business|social sciences)"
        r"[\w\s()&]*(?: in | \()(.+?)[\)]?\s*$",
        stripped_hons, re.IGNORECASE,
    )
    if m:
        return _title_case(m.group(1)), _FALLBACK_CATEGORY

    return _title_case(stripped_hons), _FALLBACK_CATEGORY


def _title_case(s: str) -> str:
    connectors = {"and", "of", "in", "the", "for", "with", "a", "an", "at", "&"}
    words = s.split()
    out = []
    for i, w in enumerate(words):
        if i > 0 and w.lower() in connectors:
            out.append(w.lower())
        else:
            out.append(w.capitalize())
    return " ".join(out)


# ─────────────────────────────────────────────
# DataFrame cleaning
# ─────────────────────────────────────────────

def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[COLUMNS]

    df["university"] = df["university"].str.strip().str.upper()
    df["school"] = df["school"].apply(lambda s: s.strip().capitalize() if isinstance(s, str) else s)

    canon_cat = df["degree"].apply(canonicalise_degree_with_category)
    df["degree"] = canon_cat.apply(lambda t: t[0])
    df["category"] = canon_cat.apply(lambda t: t[1])

    # Drop junk/footnote rows that canonicalise to blank (e.g. "Cum Laude and above"
    # with no actual degree name attached)
    df["degree"] = df["degree"].astype(str).str.strip()
    df = df[df["degree"] != ""]

    for col in COLUMNS[4:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    for col in RATE_METRICS:
        if col in df.columns:
            mask = df[col] > 1
            if mask.any():
                df.loc[mask, col] = df.loc[mask, col] / 100

    # Drop rows that are completely incomplete -- every metric column is NA,
    # so the row carries no usable data (just a degree/uni/year stub).
    # Rows with SOME valid metrics (e.g. employment rate present but salary
    # missing) are kept; only fully-empty rows are dropped.
    metric_cols = COLUMNS[4:]
    df = df[df[metric_cols].notna().any(axis=1)]

    df = df.dropna(subset=["year", "university", "degree"])
    df["year"] = df["year"].astype(int)

    # After canonicalising, consolidate duplicates within same year/university/degree
    # by averaging numeric columns
    num_cols = COLUMNS[4:]
    df = (
        df.groupby(["year", "university", "school", "degree", "category"], as_index=False)[num_cols]
        .mean()
    )
    return df.sort_values(["year", "university", "degree"]).reset_index(drop=True)


# ─────────────────────────────────────────────
# I/O helpers
# ─────────────────────────────────────────────

def load_master() -> pd.DataFrame:
    path = os.path.abspath(MASTER_PATH)
    df = pd.read_csv(path)
    return clean_dataframe(df)


def ingest_new_file(uploaded_file) -> tuple[pd.DataFrame, int, list[str]]:
    """
    Ingest a new GES CSV, merge it into the master, and return
    (merged_df, new_row_count, warnings).

    warnings is a list of human-readable strings describing any universities
    or years that were present in the uploaded file but are missing from the
    master after merging — indicating rows were silently dropped somewhere.
    An empty list means everything integrated cleanly.
    """
    new_df = pd.read_csv(uploaded_file)
    new_df = clean_dataframe(new_df)
    master = load_master()

    merged = pd.concat([master, new_df], ignore_index=True)
    merged = merged.drop_duplicates(subset=["year", "university", "degree"], keep="last")
    merged = merged.sort_values(["year", "university", "degree"]).reset_index(drop=True)

    new_rows = len(merged) - len(master)
    path = os.path.abspath(MASTER_PATH)
    merged.to_csv(path, index=False)

    # ── Post-ingest validation ──────────────────────────────────────────
    # Check every (year, university) combination in the uploaded file is
    # present in the merged master. Any missing combo means rows were lost.
    warnings: list[str] = []
    uploaded_combos = set(
        zip(new_df["year"].astype(int), new_df["university"])
    )
    merged_combos = set(
        zip(merged["year"].astype(int), merged["university"])
    )
    missing_combos = uploaded_combos - merged_combos
    for year, uni in sorted(missing_combos):
        n_lost = len(new_df[(new_df["year"] == year) & (new_df["university"] == uni)])
        warnings.append(
            f"⚠️ {uni} {year}: {n_lost} row(s) from uploaded file not found in master after merge."
        )

    return merged, new_rows, warnings


def get_categories() -> list[str]:
    return sorted(set(DEGREE_CATEGORY.values()))


def filter_by_category(df: pd.DataFrame, category: str) -> pd.DataFrame:
    """Return rows whose degree belongs to the given category (exact, not keyword-fuzzy)."""
    if "category" in df.columns:
        return df[df["category"] == category].copy()
    # Fallback if category column missing for any reason
    degrees_in_cat = {d for d, c in DEGREE_CATEGORY.items() if c == category}
    return df[df["degree"].isin(degrees_in_cat)].copy()


def get_all_degrees(df: pd.DataFrame) -> list[str]:
    degrees = df["degree"].dropna().astype(str).str.strip()
    degrees = degrees[degrees != ""]
    return sorted(degrees.unique().tolist())


def get_all_universities(df: pd.DataFrame) -> list[str]:
    return sorted(df["university"].unique().tolist())
