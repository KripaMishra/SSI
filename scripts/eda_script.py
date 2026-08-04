"""Comprehensive EDA: inconsistencies in numerical/categorical/date fields."""
import pandas as pd
import re
from collections import defaultdict

DATA = "/home/kripa/Personal/projects/SSI/Data"
REPORT = []  # accumulate findings

def log(section, finding):
    REPORT.append(f"## {section}\n{finding}\n")

# ── helpers ──────────────────────────────────────────────────────────
def fmt_counts(s):
    """return dict of value->count for a series"""
    return (s.value_counts(dropna=False).head(20).to_dict())

def check_categorical(srs, name):
    """uniques, case-sensitivity, whitespace, suspicious patterns"""
    findings = []
    uniq = srs.dropna().unique()
    total = len(srs)
    nunique = len(uniq)
    missing = srs.isna().sum()
    if missing:
        findings.append(f"- {missing}/{total} missing ({(missing/total)*100:.1f}%)")
    findings.append(f"- distinct: {nunique}")

    # skip string-specific checks if column is numeric
    is_numeric = pd.api.types.is_numeric_dtype(srs)

    # case-sensitivity: only for non-numeric categorical
    if not is_numeric:
        uniq_str = pd.Series(uniq).astype(str)
        lowered = uniq_str.str.strip().str.lower()
        # detect case-variants: two DIFFERENT original values that collapse to same lowered form
        if lowered.duplicated(keep=False).any():
            duped_lower = lowered[lowered.duplicated(keep=False)].unique()
            for lv in duped_lower:
                originals = uniq_str[lowered == lv].tolist()
                if len(originals) > 1:
                    findings.append(f"- CASE SENSITIVITY: values differ only by case → {originals}")

        # leading/trailing whitespace (check on unique values)
        ws = uniq_str.str.contains(r'^\s|\s$', regex=True)
        if ws.any():
            findings.append(f"- WHITESPACE: {ws.sum()} values have leading/trailing spaces")

        # empty strings
        empty = (uniq_str.str.strip() == '').sum()
        if empty:
            findings.append(f"- EMPTY STRINGS: {empty} values")

        # Check for unusually long strings (likely errors)
        str_len = uniq_str.str.len()
        if str_len.max() > 50:
            long_idx = str_len[str_len > 50].index[:5]
            findings.append(f"- OVERLY LONG VALUES (>50 chars): {uniq_str[long_idx].tolist()}")

    return findings

def check_numerical(srs, name):
    """outliers, negatives, zeros, missing, suspicious constants"""
    findings = []
    total = len(srs)
    missing = srs.isna().sum()
    if missing:
        findings.append(f"- {missing}/{total} missing ({(missing/total)*100:.1f}%)")

    srs_num = srs.dropna()
    if srs_num.empty:
        return findings

    # coerce to numeric
    srs_num = pd.to_numeric(srs_num, errors='coerce')
    orig_bad = srs_num.isna().sum()
    if orig_bad:
        findings.append(f"- {orig_bad} non-numeric values coerced to NaN")

    desc = srs_num.describe()
    findings.append(f"- range: [{desc['min']:.2f}, {desc['max']:.2f}]")
    findings.append(f"- mean={desc['mean']:.2f}, median={desc['50%']:.2f}")

    # negatives
    neg = (srs_num < 0).sum()
    if neg:
        findings.append(f"- NEGATIVES: {neg} values < 0")
    # zeros
    zeros = (srs_num == 0).sum()
    if zeros:
        findings.append(f"- ZEROS: {zeros} values == 0")
    # suspicious constant
    if srs_num.nunique() == 1:
        findings.append(f"- CONSTANT: all values = {srs_num.iloc[0]}")
    # top 5 extreme values
    top5 = srs_num.nlargest(5).tolist()
    bot5 = srs_num.nsmallest(5).tolist()
    findings.append(f"- top-5 values: {top5}")
    findings.append(f"- bottom-5 values: {bot5}")

    return findings

def check_dates(srs, name):
    """inconsistent date formats"""
    findings = []
    total = len(srs)
    missing = srs.isna().sum()
    if missing:
        findings.append(f"- {missing}/{total} missing")

    raw = srs.dropna().astype(str).str.strip()
    # detect format patterns
    patterns = defaultdict(list)
    for val in raw:
        # classify by regex
        if re.match(r'^\d{4}-\d{2}-\d{2}$', val):
            patterns['YYYY-MM-DD'].append(val)
        elif re.match(r'^\d{2}-\d{2}-\d{4}$', val):
            patterns['DD-MM-YYYY'].append(val)
        elif re.match(r'^\d{2}/\d{2}/\d{4}$', val):
            patterns['DD/MM/YYYY'].append(val)
        elif re.match(r'^\d{4}/\d{2}/\d{2}$', val):
            patterns['YYYY/MM/DD'].append(val)
        elif re.match(r'^\d{1,2}-\d{1,2}-\d{2}$', val):
            patterns['M-D-YY'].append(val)
        elif re.match(r'^\d{4}-\d{2}-\d{2} ', val):
            patterns['YYYY-MM-DD HH:MM...'].append(val)
        elif re.match(r'^\d{1,2} [A-Z][a-z]{2} \d{4}$', val):
            patterns['DD Mon YYYY'].append(val)
        elif re.match(r'^\d{2}/\d{2}/\d{2}$', val):
            patterns['MM/DD/YY'].append(val)
        elif re.match(r'^\d{4}-\d{2}$', val):
            patterns['YYYY-MM'].append(val)
        else:
            patterns[f'UNKNOWN: "{val}"'].append(val)

    if len(patterns) > 1:
        fmt_summary = {k: len(v) for k, v in patterns.items()}
        findings.append(f"- MULTIPLE DATE FORMATS: {fmt_summary}")

        # check if any dates are semantically invalid
        for fmt, vals in patterns.items():
            if fmt.startswith('UNKNOWN'):
                findings.append(f"  - Unparseable: {vals[:10]}")

        # also check if parsing throws errors
        parsed = pd.to_datetime(srs, errors='coerce')
        unparsed = parsed.isna().sum()
        if unparsed > missing:
            findings.append(f"- {unparsed - missing} values failed date parsing beyond NA count")
    else:
        # single format, still validate parseability
        parsed = pd.to_datetime(srs, errors='coerce')
        unparsed = parsed.isna().sum()
        if unparsed > missing:
            findings.append(f"- {int(unparsed - missing)} unparseable dates (extra beyond NA)")
            bad = srs[parsed.isna()].dropna().unique()[:5]
            findings.append(f"  - examples: {bad.tolist()}")

    return findings

def check_fk(df_child, col_child, df_parent, col_parent, label):
    """check foreign-key integrity"""
    child_vals = set(df_child[col_child].dropna().unique())
    parent_vals = set(df_parent[col_parent].dropna().unique())
    orphaned = child_vals - parent_vals
    if orphaned:
        return f"- FK VIOLATION ({label}): {len(orphaned)} values in {col_child} not found in {col_parent}. Examples: {list(orphaned)[:10]}"
    return None

# ── load all ─────────────────────────────────────────────────────────
dim_dist = pd.read_csv(f"{DATA}/dim_distributor.csv")
dim_geo   = pd.read_csv(f"{DATA}/dim_geo.csv")
dim_rep   = pd.read_csv(f"{DATA}/dim_rep.csv")
dim_sku   = pd.read_csv(f"{DATA}/dim_sku.csv")
fact_sales = pd.read_csv(f"{DATA}/fact_primary_sales.csv")
fact_targs = pd.read_csv(f"{DATA}/fact_targets.csv")
promos   = pd.read_csv(f"{DATA}/promotions.csv")
stocks   = pd.read_csv(f"{DATA}/stockouts.csv")

tables = {
    "dim_distributor": dim_dist, "dim_geo": dim_geo, "dim_rep": dim_rep,
    "dim_sku": dim_sku, "fact_primary_sales": fact_sales,
    "fact_targets": fact_targs, "promotions": promos, "stockouts": stocks
}

# ══════════════════════════════════════════════════════════════════════
# 1. GLOBAL: nulls, dups, shape
# ══════════════════════════════════════════════════════════════════════
log("1. Dataset Overview", "")
for name, df in tables.items():
    dup_rows = df.duplicated().sum()
    dup_cols = df.columns[df.T.duplicated()].tolist() if df.shape[1] > 1 else []
    null_total = df.isna().sum().sum()
    log(f"1.1 {name}", (
        f"- shape: {df.shape}\n"
        f"- duplicate rows: {dup_rows}\n"
        f"- duplicate columns: {dup_cols}\n"
        f"- total nulls: {null_total}\n"
        f"- dtypes:\n{df.dtypes.to_string()}"
    ))

# ── 2. DUPLICATE COLUMNS ACROSS TABLES ──────────────────────────────
log("2. Cross-table structural checks", "")
# column name overlaps (potential join keys)
all_cols = defaultdict(list)
for name, df in tables.items():
    for c in df.columns:
        all_cols[c].append(name)
shared = {c: tbls for c, tbls in all_cols.items() if len(tbls) > 1}
if shared:
    for c, tbls in sorted(shared.items()):
        log(f"2.1 Shared column '{c}'", f"present in: {tbls}")
else:
    log("2.1 Shared columns", "none (no overlapping column names across tables)")

# ── 3. CATEGORICAL FIELD DEEP-DIVE ──────────────────────────────────
log("3. Categorical field analysis", "")
cat_config = {
    "dim_distributor": ["distributor_id", "distributor_name", "territory"],
    "dim_geo": ["territory", "region"],
    "dim_rep": ["rep_id", "rep_name", "territory"],
    "dim_sku": ["sku_code", "category", "brand", "sku_name", "pack_size", "flavour", "tier"],
    "fact_primary_sales": ["sku_code", "territory", "distributor_id"],
    "fact_targets": ["material_no", "area"],
    "promotions": ["sku", "territory", "promo_type"],
    "stockouts": ["item_code", "territory", "stockout_flag"],
}
for tbl, cols in cat_config.items():
    df = tables[tbl]
    for c in cols:
        if c not in df.columns:
            continue
        findings = check_categorical(df[c], c)
        uniq_smpl = df[c].dropna().unique()[:10].tolist()
        log(f"3.{tbl}.{c}", "\n".join(findings) + f"\n- sample values: {uniq_smpl}")

# ── 4. NUMERICAL FIELD DEEP-DIVE ────────────────────────────────────
log("4. Numerical field analysis", "")
num_config = {
    "dim_sku": ["base_mrp"],
    "fact_primary_sales": ["primary_sales_units", "primary_sales_value"],
    "fact_targets": ["target_value"],
    "promotions": ["promo_discount_pct"],
    "stockouts": ["stockout_days"],
}
for tbl, cols in num_config.items():
    df = tables[tbl]
    for c in cols:
        if c not in df.columns:
            continue
        findings = check_numerical(df[c], c)
        log(f"4.{tbl}.{c}", "\n".join(findings))

# ── 5. DATE FIELD DEEP-DIVE ─────────────────────────────────────────
log("5. Date field analysis", "")
date_config = {
    "fact_primary_sales": ["week_start"],
    "fact_targets": ["month"],
    "promotions": ["week_start"],
    "stockouts": ["week_start"],
}
for tbl, cols in date_config.items():
    df = tables[tbl]
    for c in cols:
        if c not in df.columns:
            continue
        findings = check_dates(df[c], c)
        log(f"5.{tbl}.{c}", "\n".join(findings))

# ── 6. FK / REFERENTIAL INTEGRITY ───────────────────────────────────
log("6. Referential integrity checks", "")
fk_checks = [
    (fact_sales, "sku_code", dim_sku, "sku_code", "fact_primary_sales.sku_code → dim_sku.sku_code"),
    (fact_sales, "territory", dim_geo, "territory", "fact_primary_sales.territory → dim_geo.territory"),
    (fact_sales, "distributor_id", dim_dist, "distributor_id", "fact_primary_sales.distributor_id → dim_distributor.distributor_id"),
    (fact_targs, "material_no", dim_sku, "sku_code", "fact_targets.material_no → dim_sku.sku_code"),
    (fact_targs, "area", dim_geo, "territory", "fact_targets.area → dim_geo.territory"),
    (promos, "sku", dim_sku, "sku_code", "promotions.sku → dim_sku.sku_code"),
    (promos, "territory", dim_geo, "territory", "promotions.territory → dim_geo.territory"),
    (stocks, "item_code", dim_sku, "sku_code", "stockouts.item_code → dim_sku.sku_code"),
    (stocks, "territory", dim_geo, "territory", "stockouts.territory → dim_geo.territory"),
    (dim_rep, "territory", dim_geo, "territory", "dim_rep.territory → dim_geo.territory"),
    (dim_dist, "territory", dim_geo, "territory", "dim_distributor.territory → dim_geo.territory"),
]
for child, ccol, parent, pcol, label in fk_checks:
    res = check_fk(child, ccol, parent, pcol, label)
    if res:
        log("6. FK", res)

# ── 7. DUPLICATE ROWS WITHIN TABLES (by logical key) ────────────────
log("7. Logical duplicate analysis", "")
key_config = {
    "fact_primary_sales": ["week_start", "sku_code", "territory", "distributor_id"],
    "fact_targets": ["month", "material_no", "area"],
    "promotions": ["week_start", "sku", "territory"],
    "stockouts": ["week_start", "item_code", "territory"],
}
for tbl, keys in key_config.items():
    df = tables[tbl]
    all_keys_present = all(k in df.columns for k in keys)
    if not all_keys_present:
        missing = [k for k in keys if k not in df.columns]
        log(f"7.{tbl}", f"cannot check: missing keys {missing}")
        continue
    dups = df.duplicated(subset=keys, keep=False)
    n_dup = dups.sum()
    if n_dup:
        log(f"7.{tbl}", f"- {n_dup} rows ({dups.sum()/len(df)*100:.1f}%) are duplicates on composite key {keys}")
    else:
        log(f"7.{tbl}", f"- No logical duplicates on {keys}")

# ── 8. CASE SENSITIVITY CROSS-TABLE JOIN IMPACT ─────────────────────
log("8. Case-sensitivity cross-table impact", "")
# Check if territories etc. use consistent casing across tables
def case_mismatch(srs_a, srs_b, label_a, label_b, col):
    """Report when same logical value appears with different casing across two tables"""
    set_a = set(srs_a.dropna().str.strip().unique())
    set_b = set(srs_b.dropna().str.strip().unique())
    lower_a = set(v.lower() for v in set_a)
    lower_b = set(v.lower() for v in set_b)
    common = lower_a & lower_b
    issues = []
    for val_lower in common:
        reps_in_a = [v for v in set_a if v.lower() == val_lower]
        reps_in_b = [v for v in set_b if v.lower() == val_lower]
        # if the actual string isn't the same in both tables -> mismatch
        if set(reps_in_a) != set(reps_in_b):
            issues.append(f"'{reps_in_a}' vs '{reps_in_b}'")
    return issues

case_pairs = [
    (fact_sales, "territory", "fact_primary_sales", dim_geo, "territory", "dim_geo"),
    (fact_sales, "territory", "fact_primary_sales", dim_rep, "territory", "dim_rep"),
    (fact_sales, "territory", "fact_primary_sales", dim_dist, "territory", "dim_dist"),
    (promos, "territory", "promotions", dim_geo, "territory", "dim_geo"),
    (stocks, "territory", "stockouts", dim_geo, "territory", "dim_geo"),
    (fact_targs, "area", "fact_targets", dim_geo, "territory", "dim_geo"),
]
for df1, c1, l1, df2, c2, l2 in case_pairs:
    issues = case_mismatch(df1[c1], df2[c2], l1, l2, c1)
    if issues:
        log(f"8. Case: {l1}.{c1} ↔ {l2}.{c2}", f"mismatches: {issues}")
    else:
        pass  # clean

# ── 9. SUMMARY ──────────────────────────────────────────────────────
log("9. Summary of flagged issues", "See findings above for flagged fields requiring attention.")

# ── print report ────────────────────────────────────────────────────
print("\n\n".join(REPORT))
