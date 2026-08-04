"""
Preprocessing pipeline for SSI dataset.

Fixes documented in internal/eda-findings.md.
Output: Data/cleaned/ (ingestion copy), Data/omitted/ (sliced-off rows with reasons).
"""
import pandas as pd
import re
from pathlib import Path

from src.utils.logger import get_logger

logger = get_logger(__name__)

# ── paths ────────────────────────────────────────────────────────────
RAW   = Path("/home/kripa/Personal/projects/SSI/Data")
CLEAN = Path("/home/kripa/Personal/projects/SSI/cleaned")
OMIT  = Path("/home/kripa/Personal/projects/SSI/omitted")
CLEAN.mkdir(exist_ok=True)
OMIT.mkdir(exist_ok=True)

# ── helpers ──────────────────────────────────────────────────────────
def extract_numeric_sales_value(srs):
    """Remove 'Rs ' prefix and commas, then cast to float."""
    def _clean(v):
        if pd.isna(v):
            return None
        v = str(v).strip()
        if v.startswith("Rs "):
            v = v[3:]
        v = v.replace(",", "")
        try:
            return float(v)
        except ValueError:
            return None
    return srs.apply(_clean)

def normalize_week_start(srs):
    """Normalize multiple date formats to YYYY-MM-DD."""
    def _norm(v):
        if pd.isna(v):
            return None
        v = str(v).strip()
        # YYYY-MM-DD -> already correct
        if re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            return v
        # DD-MM-YYYY
        m = re.match(r"^(\d{2})-(\d{2})-(\d{4})$", v)
        if m:
            return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
        # MM/DD/YY
        m = re.match(r"^(\d{2})/(\d{2})/(\d{2})$", v)
        if m:
            yy = "20" + m.group(3)
            return f"{yy}-{m.group(1)}-{m.group(2)}"
        # DD Mon YYYY e.g. "01 Jul 2025"
        month_map = {
            "jan": "01", "feb": "02", "mar": "03", "apr": "04",
            "may": "05", "jun": "06", "jul": "07", "aug": "08",
            "sep": "09", "oct": "10", "nov": "11", "dec": "12",
        }
        m = re.match(r"^(\d{1,2})\s+(\w{3})\s+(\d{4})$", v, re.IGNORECASE)
        if m:
            day = m.group(1).zfill(2)
            mon = month_map.get(m.group(2).lower())
            if mon:
                return f"{m.group(3)}-{mon}-{day}"
        return v  # fallback: leave as-is
    return srs.apply(_norm)

# ══════════════════════════════════════════════════════════════════════
# 1. LOAD RAW
# ══════════════════════════════════════════════════════════════════════
dim_dist   = pd.read_csv(RAW / "dim_distributor.csv", dtype=str)
dim_geo    = pd.read_csv(RAW / "dim_geo.csv", dtype=str)
dim_rep    = pd.read_csv(RAW / "dim_rep.csv", dtype=str)
dim_sku    = pd.read_csv(RAW / "dim_sku.csv", dtype=str)
fact_sales = pd.read_csv(RAW / "fact_primary_sales.csv", dtype=str)
fact_targs = pd.read_csv(RAW / "fact_targets.csv", dtype=str)
promos     = pd.read_csv(RAW / "promotions.csv", dtype=str)
stocks     = pd.read_csv(RAW / "stockouts.csv", dtype=str)

tables = {
    "dim_distributor": dim_dist,
    "dim_geo": dim_geo,
    "dim_rep": dim_rep,
    "dim_sku": dim_sku,
    "fact_primary_sales": fact_sales,
    "fact_targets": fact_targs,
    "promotions": promos,
    "stockouts": stocks,
}

logger.info("loaded raw tables", extra={k: len(v) for k, v in tables.items()})

# ══════════════════════════════════════════════════════════════════════
# 2. PER-TABLE TRANSFORMATIONS
# ══════════════════════════════════════════════════════════════════════

# ── 2a. dim_geo ──────────────────────────────────────────────────────
# Fix: Bombay -> Mumbai, S -> South, E -> East
dim_geo["territory"] = dim_geo["territory"].str.replace("Bombay", "Mumbai", regex=False)
region_map = {"S": "South", "E": "East"}
dim_geo["region"] = dim_geo["region"].replace(region_map)
logger.info("dim_geo: transformed", extra={"territories": dim_geo["territory"].nunique(), "regions": dim_geo["region"].unique().tolist()})

# ── 2b. dim_sku ──────────────────────────────────────────────────────
# Fix: whitespace on sku_code
dim_sku["sku_code"] = dim_sku["sku_code"].str.strip()
# Fix: tier -> lowercase, VAL->value, PREM->premium
dim_sku["tier"] = dim_sku["tier"].str.lower()
tier_map = {"val": "value", "prem": "premium"}
dim_sku["tier"] = dim_sku["tier"].replace(tier_map)
logger.info("dim_sku: transformed", extra={"skus": len(dim_sku), "tiers": dim_sku["tier"].unique().tolist()})

# ── 2c. dim_rep ──────────────────────────────────────────────────────
# Fix: missing rep_name for SO-04 -> "Officer 4"
dim_rep["rep_name"] = dim_rep.apply(
    lambda r: f"Officer {int(r['rep_id'].split('-')[1])}" if pd.isna(r["rep_name"]) else r["rep_name"],
    axis=1,
)
logger.info("dim_rep: filled missing names", extra={"reps": len(dim_rep)})

# ── 2d. dim_distributor ──────────────────────────────────────────────
# No structural transformations needed (territory mapping happens at join time)

# ── 2e. fact_primary_sales ───────────────────────────────────────────
# Fix 1: week_start normalize to YYYY-MM-DD
fact_sales["week_start"] = normalize_week_start(fact_sales["week_start"])

# Fix 2: distributor_id - strip leading '0' prefix
fact_sales["distributor_id"] = fact_sales["distributor_id"].str.lstrip("0")

# Fix 3: territory mapping (BLR/BGL -> Bengaluru; Mumbai handled via dim_geo)
fact_sales["territory"] = fact_sales["territory"].replace({"BLR": "Bengaluru", "BGL": "Bengaluru"})

# Fix 4: primary_sales_value - extract numeric from string patterns
fact_sales["primary_sales_value"] = extract_numeric_sales_value(fact_sales["primary_sales_value"])

# Fix 5: primary_sales_units - add negative flag
fact_sales["primary_sales_units"] = pd.to_numeric(fact_sales["primary_sales_units"], errors="coerce")
fact_sales["sales_units_flag"] = "ok"
fact_sales.loc[fact_sales["primary_sales_units"] < 0, "sales_units_flag"] = "negative"
neg_count = (fact_sales["sales_units_flag"] == "negative").sum()
logger.info("fact_primary_sales: transformed", extra={"rows": len(fact_sales), "negative_units": int(neg_count)})

# ── 2f. fact_targets ─────────────────────────────────────────────────
# Fix: area -> territory mapping (Mumbai handled via dim_geo)
fact_targs["area"] = fact_targs["area"].replace({"Mumbai": "Mumbai"})  # already consistent, no-op
# Territory mapping for area column
fact_targs["area"] = fact_targs["area"].replace({"BLR": "Bengaluru", "BGL": "Bengaluru"})

# ── 2g. promotions ───────────────────────────────────────────────────
# Fix: territory mapping
promos["territory"] = promos["territory"].replace({"BLR": "Bengaluru", "BGL": "Bengaluru"})

# ── 2h. stockouts ────────────────────────────────────────────────────
# Fix: territory mapping
stocks["territory"] = stocks["territory"].replace({"BLR": "Bengaluru", "BGL": "Bengaluru"})

# ══════════════════════════════════════════════════════════════════════
# 3. SPLIT OMITTED ROWS (sliced-off with reasons)
# ══════════════════════════════════════════════════════════════════════

# ── 3a. fact_primary_sales: duplicate rows on logical key ────────────
key_cols = ["week_start", "sku_code", "territory", "distributor_id"]
dup_mask = fact_sales.duplicated(subset=key_cols, keep=False)
dups = fact_sales[dup_mask].copy()
dups["omitted_reason"] = f"duplicate on composite key {key_cols}"
fact_sales = fact_sales[~dup_mask].copy()

# ── 3b. promotions: territory="North" is a region, not a territory ───
promo_omit = promos[promos["territory"] == "North"].copy()
promo_omit["omitted_reason"] = "territory='North' is a region code, not a valid territory"
promos = promos[promos["territory"] != "North"].copy()

# ══════════════════════════════════════════════════════════════════════
# 4. SAVE CLEANED (CSV only — parquet engine not available)
# ══════════════════════════════════════════════════════════════════════
fact_sales.to_csv(CLEAN / "fact_primary_sales.csv", index=False)
fact_targs.to_csv(CLEAN / "fact_targets.csv", index=False)
dim_sku.to_csv(CLEAN / "dim_sku.csv", index=False)
dim_geo.to_csv(CLEAN / "dim_geo.csv", index=False)
dim_rep.to_csv(CLEAN / "dim_rep.csv", index=False)
dim_dist.to_csv(CLEAN / "dim_distributor.csv", index=False)
promos.to_csv(CLEAN / "promotions.csv", index=False)
stocks.to_csv(CLEAN / "stockouts.csv", index=False)

# ══════════════════════════════════════════════════════════════════════
# 5. SAVE OMITTED
# ══════════════════════════════════════════════════════════════════════
if not dups.empty:
    dups.to_csv(OMIT / "fact_primary_sales_duplicates.csv", index=False)
if not promo_omit.empty:
    promo_omit.to_csv(OMIT / "promotions_north_territory.csv", index=False)

# ══════════════════════════════════════════════════════════════════════
# 6. SUMMARY
# ══════════════════════════════════════════════════════════════════════
logger.info("preprocessing complete", extra={
    "cleaned_dir": str(CLEAN),
    "tables": {name: len(df) for name, df in tables.items()},
    "omitted": {
        "fact_primary_sales_duplicates": len(dups) if not dups.empty else 0,
        "promotions_north_territory": len(promo_omit) if not promo_omit.empty else 0,
    },
})