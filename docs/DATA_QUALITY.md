# Sales Data Quality: Anomaly Catalogue

Catalogue of every sales-data anomaly class found during EDA and cleaning of the SSI
assessment dataset (raw `Data/`, cleaned `cleaned/`). Written for issue #2 to close
limitation #2 of `APPROACH.md` ("many sales number anomalies lack documentation").

**Scope.** 8 source tables; 52 weeks (2025-07-01 → 2026-06-23); 134 SKUs; 12 territories.
Raw `fact_primary_sales`: **61,955 rows** → cleaned: **61,932 rows** (= 52 weeks × 1,191
rows/week exactly). All counts below were measured by re-running the repo EDA scripts and
supplementary read-only checks on the current files (see [Method](#method-and-verification));
counts that correct `APPROACH.md`/`ARTEFACT.md` are marked **†**.

---

## Summary

| # | Anomaly class | Rows affected (raw) | Status |
|---|---|---|---|
| 1 | Multi-format `week_start` dates | 10,972 | fixed |
| 2 | Non-numeric `primary_sales_value` (`Rs ` / commas) | 9,416 | fixed |
| 3 | Sentinel volumes 9999 / -9999 | 772 | nulled + flagged |
| 4 | Negative volumes (returns ambiguity) | 735 | nulled + flagged |
| 5 | Duplicate fact rows (23 pairs) | 46 (23 kept) | deduped |
| 6 | Territory aliases BLR / BGL / Bombay | 4,890 fact + 1 dim row | fixed |
| 7 | Distributor ID leading zeros | 9,382 **†** | fixed |
| 8 | Master-dimension inconsistencies (tier, region, rep_name) | 8+2+1 values | fixed |
| 9 | `dim_sku` duplicated master rows (case/whitespace) | 2 logical SKUs | **NOT addressed** |
| 10 | Value/units inconsistency (implied price ≫ MRP) | 16 | **NOT addressed** |
| 11 | Synthetic value construction (0.75 × MRP × units) | 59,319 of 59,348 | informational |
| 12 | Diffuse missing units | 2,186 | nulled (value kept) |
| 13 | Outlier weeks (Oct 2025 festival block) | 4 weeks, z≈3 | **NOT addressed** |
| 14 | Right-skewed units distribution | whole table | informational |
| 15 | Target/sales calibration (corr 0.995) | 14,292 targets | informational |
| 16 | Absent SKU×territory combos (74 % grid coverage) | 417 combos | **NOT addressed** |
| 17 | Sparse support tables (promotions 2, stockouts 2) | 2 + 2 | structural |
| 18 | Zero units / zero values / sub-0.5 prices | 0 | checked — clean |

---

## Part A — Documented classes (verified counts)

### 1. Multi-format `week_start` dates — fixed
- **Pattern:** four lexical formats in one column.
- **Affected:** `fact_primary_sales.week_start` (only this table; `fact_targets.month`,
  `promotions.week_start`, `stockouts.week_start` are each single-format).
- **Counts (raw):** `YYYY-MM-DD` 50,983; `MM/DD/YY` 3,734; `DD Mon YYYY` 3,665;
  `DD-MM-YYYY` 3,573 → 10,972 non-ISO rows (17.7 %).
- **Current handling:** normalized to `YYYY-MM-DD`; cleaned table parses to exactly 52
  unique weeks with zero unparseable residue.
- **Salvage:** none needed — lossless fix.

### 2. Non-numeric `primary_sales_value` — fixed
- **Pattern:** value stored as `"Rs 34,808"` (prefix + thousands comma) or bare `"34,808"`.
  Exactly two lexical forms; every one of the 9,416 non-numeric values contains exactly one
  comma; no multi-comma values.
- **Affected:** `fact_primary_sales.primary_sales_value`.
- **Counts:** 9,416 of 61,955 rows (15.2 %) — split **4,709** `Rs a,b` / **4,707** bare
  `a,b` **†** (see method note: `analyze_sales_value_patterns.py` prints per-pattern counts
  of 1/1 due to a dict-overwrite bug; the true split is ~half/half).
- **Current handling:** strip `"Rs "` and commas → float. Cleaned column is `float64` with
  0 non-numeric residue.
- **Salvage:** none needed — lossless fix (all forms unambiguously parseable).

### 3. Sentinel volumes 9999 / -9999 — nulled + flagged
- **Pattern:** implausible constant volumes `9999` (771 rows) and `-9999` (1 row). Real
  volume tail is p99 = 1,400, max = 1,895, so 9999 is far outside any plausible reading.
- **Affected:** `fact_primary_sales.primary_sales_units`.
- **Counts:** 771 × `9999`, 1 × `-9999`. Spread is diffuse: top territory Mumbai 75,
  Guwahati 72, Delhi 72, Patna 71; top SKU HC-006 16, CO-005 14 — no systematic cluster.
- **Current handling:** → NULL, `sales_units_flag = 'sentinel_9999' / 'sentinel_-9999'`.
- **Salvage:** *partially.* The retained `primary_sales_value` implies the sentinel rows had
  realistic volumes: `value / (0.75 × base_mrp)` median ≈ **452 units** (vs. dataset median
  584) — i.e. the sentinel replaced a plausible mid-sized quantity, and the value column
  remains usable. Only source context (why the export wrote 9999) could recover the exact
  volume.

### 4. Negative volumes — nulled + flagged (returns ambiguity)
- **Pattern:** `primary_sales_units < 0` — 735 rows raw (734 negatives + the `-9999` above).
- **Affected:** `fact_primary_sales.primary_sales_units`.
- **Counts:** 735; diffuse — top territory Pune 75, Jaipur 65, Ahmedabad 63, Delhi 63,
  Guwahati 61; top SKU SL-002 15, MM-006 13.
- **Current handling:** → NULL, `sales_units_flag = 'negative'`. Per `ARTEFACT.md` they are
  treated as data errors, **not** returns (no returns dimension exists), so gross sales are
  never netted down.
- **Salvage:** *yes, with a returns/credit-note table* — negatives are a classic returns
  signature. Absent that table, nulling is the defensible choice.

### 5. Duplicate fact rows — deduped
- **Pattern:** exact duplicates on composite key `(week_start, sku_code, territory,
  distributor_id)`.
- **Counts:** 46 rows = **23 pairs**; 23 kept, 23 moved to `omitted/fact_primary_sales_duplicates.csv`.
- **Affected:** `fact_primary_sales`. No logical duplicates in `fact_targets`,
  `promotions`, `stockouts`.
- **Current handling:** keep-first.
- **Salvage:** none needed — pairs are exact copies.

### 6. Territory aliases BLR / BGL / Bombay — fixed
- **Pattern:** `dim_geo` used `Bombay` while every other table used `Mumbai`; `fact_primary_sales`
  used airport codes `BLR`, `BGL` for Bengaluru.
- **Affected:** `fact_primary_sales.territory`, `dim_geo.territory`
  (dim_rep / dim_distributor were already `Mumbai` — they were FK-violating against
  `dim_geo.Bombay` before the rename).
- **Counts:** fact rows — `BLR` **2,538**, `BGL` **2,352**, `Mumbai` 5,408 (already
  canonical); `dim_geo` `Bombay` 1 row. **4,890 fact rows renamed †** — `APPROACH.md`'s
  "~190 rows across 4 tables" understates the fact-table impact by ~25×.
- **Current handling:** mapped to `Bengaluru` / `Mumbai`; cleaned: 12 territories, FK-clean.
- **Salvage:** none needed.

### 7. Distributor ID leading zeros — fixed
- **Pattern:** half the distributor IDs appeared as `0DEL-D1` (zero-prefixed) alongside
  clean `DEL-D1`.
- **Affected:** `fact_primary_sales.distributor_id`.
- **Counts:** **24 distinct zero-prefixed IDs covering 9,382 rows (15.1 %)** † —
  `APPROACH.md` lists "24 IDs" with no row count; the row-level impact is 15 % of the fact
  table, not a rounding detail.
- **Current handling:** `lstrip('0')`; cleaned: 24 distinct distributors, FK-clean.
- **Salvage:** none needed — prefix is purely lexical (export zero-padding).

### 8. Master-dimension inconsistencies — fixed
- **Pattern/Counts:** `dim_sku.tier` 8 spellings → 3 (`VAL`/`PREM` lowercase, case-variant
  `Mainstream`/`Premium`/`Value`); `dim_geo.region` `S`/`E` → `South`/`East` (2 values);
  `dim_rep.rep_name` 1 missing (8.3 % of 12) filled from `rep_id`; `promotions` row with
  `territory = "North"` (a region, not a territory — FK violation) → 1 row omitted.
- **Current handling:** normalized as documented.
- **Salvage:** none needed.

---

## Part B — Newly surfaced classes (beyond APPROACH.md)

### 9. `dim_sku` duplicated master rows — NOT addressed
- **Pattern:** `GJ-001` / `GJ-002` each exist twice: canonical uppercase, plus a lowercase
  trailing-space variant `gj-001 ` / `gj-002 ` (same `sku_name`, same MRP).
- **Affected:** `dim_sku.sku_code` (136 rows, but only 134 logical SKUs).
- **Counts:** 2 duplicated logical SKUs = 2 surplus rows.
- **Current handling:** none — cleaned `dim_sku.csv` still carries all 136 rows. Harmless to
  FK checks (the variant rows are never referenced by facts) but **join-fragile**: any
  case-sensitive join that picks the variant row silently detaches GlucoJoy 50g/Choco 50g
  from sales.
- **Salvage:** yes — dedupe on `lower(strip(sku_code))`; source master export should be
  deduplicated.
- **Repro:** see [Not addressed — repro](#not-addressed--repro-steps).

### 10. Value/units inconsistency — 16 rows, NOT addressed
- **Pattern:** `primary_sales_value / (units × base_mrp)` should be ≈0.75 everywhere
  (see §11); 16 rows sit at **18.3–27.5×**, i.e. the value implies ~24–27× the recorded
  units (recorded units are all small: 4–58).
- **Affected:** `fact_primary_sales` (both columns).
- **Counts:** 16 of 59,348 valid rows (0.03 %); scattered over 15 different weeks and 10
  territories (e.g. `NB-007` Guwahati 2026-05-12: 4 units vs ₹4,950 ≈ 110 implied units;
  `PF-009` Delhi 2025-09-23: 7 units vs ₹22,680 ≈ 189 implied units).
- **Current handling:** **none** — no flag column covers value anomalies; these rows flow
  into value aggregates with ~25× inflated value. (Unit aggregates are unaffected — the
  national total of 38,630,596 units stands.)
- **Salvage:** *yes.* 13 of 16 rows imply a quantity ≈ 24× recorded (24.0–24.7×), consistent
  with **case-level entry where a case = 24 packs**; 3 rows are 25.0–27.5× (unexplained).
  Pack/case conversion factors from the source system would resolve them; absent that, they
  should at least be flagged like the unit flags.
- **Repro:** see below.

### 11. Synthetic value construction — informational caveat
- **Pattern:** `primary_sales_value = 0.75 × base_mrp × primary_sales_units` for
  essentially the whole dataset: **54,853 of 59,348 valid rows exactly 0.75×**; a further
  4,466 rows within ±₹1 rounding (ratio 0.7498–0.751); 13 rows 0.75–0.94; 16 rows §10.
  Nothing between 0.94 and 18.3 — zero rows in (1.0, 2.5], zero rows < 0.5.
- **Implication:** value carries no independent information beyond `units × MRP` (flat 25 %
  trade discount). Any "average realization", "price" or "margin" analysis will find a
  constant 0.75 by construction. Not an error — a data-generation property — but it caps
  what value-based WHY analysis can conclude.
- **Current handling:** none needed; documented so downstream analysis doesn't over-read.
- **Salvage:** only real invoicing data would change this.

### 12. Diffuse missing units — nulled (value retained)
- **Pattern:** `primary_sales_units` NA; `primary_sales_value` always present (2,186/2,186).
- **Affected:** `fact_primary_sales`.
- **Counts:** 2,186 raw (3.5 %); cleaned 3,692 (6.0 %) after §3/§4 nulling. Distribution is
  flat: 25–47 nulls/week (mean 34.8), 189–203 per territory, top SKU 29 — no temporal or
  geographic cluster, consistent with random omission.
- **Current handling:** left NULL (flag `ok`-excluded); value kept.
- **Salvage:** *yes in principle* — given §11's price construction, value / (0.75 × MRP)
  recovers units to within rounding; but that is exactly the kind of derived-imputation that
  this project chose to avoid. Better source context = the export that dropped the volumes.

### 13. Outlier weeks — Oct 2025 festival block, NOT addressed
- **Pattern:** national weekly units (valid rows only) spike +2.9–3.0σ for **four
  consecutive weeks** — 2025-10-07 … 2025-10-28 (678k–681k vs ~600k baseline). Lowest weeks:
  2026-03-03 (584k), 2025-07-22 (585k). Single-territory extreme: Mumbai 2025-10-07 at 3.3σ.
- **Interpretation:** a 4-week sustained block is a **seasonal uplift, not a data error** —
  it brackets Diwali (20 Oct 2025). It is flagged here because the agent has no promotion or
  event data covering it (§17) and will otherwise report "Oct spike" as unexplained.
- **Current handling:** none — no flagging, no documentation in the prompt corpus.
- **Salvage:** yes — a festival/event calendar or Oct promotions from source would confirm
  attribution. Note 2025-09-16 is also elevated (629,829) — that week carries the only
  usable promo row (§17).
- **Repro:** see below.

### 14. Right-skewed units distribution — informational
- **Pattern:** units mean 785 vs median 584 (raw valid) — moderate right skew. Per category:
  Snacks 907/945 (mild left), Tea 727/721 (symmetric), Biscuits 562/488, Shampoo 573/488,
  Detergent 610/516 (right-skewed).
- **Concentration:** low — top-5 SKUs = 8.0 % of national units, top-1 = 1.6 %; no
  single-SKU or single-category dominance that would distort aggregates.
- **Current handling:** none needed.
- **Salvage:** n/a.

### 15. Target/sales calibration — informational caveat
- **Pattern:** `fact_targets` and `fact_primary_sales` universes are **identical**: same 134
  SKUs, same 12 areas, 1,191 combos per month = 1,191 rows per week; 100 % of target rows
  join to sales; monthly sales/target ratio mean 0.982, std 0.046, per-month 0.951–0.993;
  correlation 0.9952.
- **Implication:** targets are derived from actuals — **achievement is ~95–99 % by
  construction**. "Missed target" analysis will find only the mild Oct–Dec under-achievement
  (0.951–0.956, i.e. targets set above the festival peak), never a structural miss.
- **Current handling:** none; caveat for downstream.
- **Salvage:** real target-setting process data (budgets before actuals).

### 16. Absent SKU×territory combos — 74 % grid coverage, NOT addressed
- **Pattern:** the fact grid has **417 of 1,608** possible SKU×territory combos absent
  (74 % present) — every present combo appears all 52 weeks (rectangular).
- **Shape:** SKUs sell in 5–12 territories (`CR-007/008/009`, `MG-007/008/009` in only 5);
  26 SKUs in all 12; fewest SKUs per territory: Chennai 87, Kolkata 93, Bengaluru/Lucknow 94.
  Targets mirror the same 1,191 combos — the absence is structural, not a missing-data hole.
- **Ambiguity:** an absent combo is indistinguishable from "not distributed" vs "no sales in
  window". Any "SKU X has zero sales in Y" conclusion is unsafe.
- **Current handling:** none (no `zero` flag exists — appropriate, since these aren't
  recorded zeros).
- **Salvage:** yes — distribution footprint (which SKUs each distributor stocks) from source
  would resolve the ambiguity.
- **Repro:** see below.

### 17. Sparse support tables — promotions (2 rows) / stockouts (2 rows)
- **Pattern:** the entire 52-week × 1,191-combo window has **2 promotion rows** (1 usable:
  `SC-004` Mumbai 15 % on 2025-09-16; 1 omitted for invalid territory) and **2 stockout
  rows** (`GJ-003` Delhi 2025-11-11 flag=1 days=5; `CO-004` Chennai 2026-03-10 flag=1
  days=4).
- **Cross-validation (positive):** the stockout weeks show deep sales dips — `GJ-003` Delhi
  22 units vs median 521 (−96 %); `CO-004` Chennai 30 vs 537 (−94 %) — so the stockout rows
  are credible where present. The one promo week (`SC-004` Mumbai) is that SKU's max week
  (673 vs median 517, +30 %).
- **Limitation:** with 1 promo and 2 stockouts, neither table can explain the Oct 2025
  national peak (§13) or general variance. Absence of promotion coverage ≠ absence of
  promotions.
- **Current handling:** North promo omitted to `omitted/`; tables loaded as-is.
- **Salvage:** yes — full promo/stockout calendars from source would enable the causal layer.

### 18. Checked and clean (no anomaly found)
- Zero `primary_sales_units` rows: **0**; zero `primary_sales_value`: **0**.
- Values with >1 comma: **0**; implied-price ratio < 0.5: **0**.
- Case-variant mismatches across tables (EDA §8): **0**.
- Duplicate rows in `fact_targets` / `promotions` / `stockouts`: **0**.
- Unparseable dates after cleaning: **0** (52 unique weeks).
- FK violations after cleaning: **0** (territories, SKUs, distributors all resolve).

---

## Not addressed — repro steps

All repro commands run from repo root with `.venv/bin/python`; none write files.

**§9 `dim_sku` duplicated master rows**
```python
import pandas as pd
sku = pd.read_csv('Data/dim_sku.csv')
n = sku['sku_code'].str.strip().str.lower()
print(len(sku), sku['sku_code'].nunique(), n.nunique())   # 136 136 134
print(sku[n.duplicated(keep=False)][['sku_code','sku_name','base_mrp']])
```

**§10 value/units inconsistencies (16 rows)**
```python
import pandas as pd
raw = pd.read_csv('Data/fact_primary_sales.csv')
sku = pd.read_csv('Data/dim_sku.csv')
raw['val'] = pd.to_numeric(raw['primary_sales_value'].str.replace('Rs ','',regex=False)
                           .str.replace(',','',regex=False), errors='coerce')
u = raw['primary_sales_units']
ok = raw[(u > 0) & (u < 9999)].copy()
ok['code'] = ok['sku_code'].str.strip().str.lower()
mrp = dict(zip(sku['sku_code'].str.strip().str.lower(), sku['base_mrp']))
ok['ratio'] = ok['val'] / ok['primary_sales_units'] / ok['code'].map(mrp)
print(len(ok[ok['ratio'] > 2.5]))                          # 16
print(ok[ok['ratio'] > 2.5][['week_start','sku_code','territory','primary_sales_units','primary_sales_value']])
```

**§11 value construction**
```python
# same prep as §10; then:
r = ok['val'] / ok['primary_sales_units'] / ok['code'].map(mrp)
print((r.round(6) == 0.75).sum(), r.quantile([.01,.5,.99]).round(4).to_dict())  # 54853 / 0.75,0.75,0.75
```

**§13 outlier weeks**
```python
import pandas as pd
raw = pd.read_csv('Data/fact_primary_sales.csv')
raw['d'] = pd.to_datetime(raw['week_start'], errors='coerce')
u = raw['primary_sales_units']
v = raw[(u > 0) & (u < 9999)]
wk = v.groupby('d')['primary_sales_units'].sum()
z = (wk - wk.mean()) / wk.std()
print(z[z.abs() > 2.5])     # 2025-10-07..10-28 block, z ≈ 2.9-3.0
```

**§16 absent combos**
```python
import pandas as pd
cln = pd.read_csv('cleaned/fact_primary_sales.csv')
combos = set(zip(cln['sku_code'], cln['territory']))
allc = [(s, t) for s in cln['sku_code'].unique() for t in cln['territory'].unique()]
print(len(allc) - len(combos))          # 417
print(cln.groupby('sku_code')['territory'].nunique().min())   # 5
```

**§15 target calibration**
```python
import pandas as pd
tgt = pd.read_csv('Data/fact_targets.csv')
print(tgt.groupby('month').size().unique())   # [1191] = sales rows/week
# join monthly sales value to targets; ratio ≈ 0.95-0.99, corr ≈ 0.995
```

---

## Method and verification

- Ran `scripts/eda_script.py` and `scripts/analyze_sales_value_patterns.py` unmodified
  (`.venv/bin/python`, both exit 0) against `Data/` + `cleaned/`, plus the read-only
  checks above. Scripts were **not** modified; exploration code lives outside the repo.
- **Known script bug (reported, not fixed):** `analyze_sales_value_patterns.py` builds
  `patterns[wrapper]` and overwrites on every distinct value sharing a wrapper, so its
  per-pattern `count` (printed 1/1) undercounts — true split is 4,709 / 4,707. The
  wrapper taxonomy (2 forms) and the 9,416 total are correct.
- **Cross-checks vs ARTEFACT.md:** flag counts `ok` 60,426 + `sentinel_9999` 771 +
  `negative` 734 + `sentinel_-9999` 1 = 61,932 = cleaned rows = 52 × 1,191 ✓; the 23
  omitted duplicates and the 1,506 nulled rows reconcile ✓; national units total
  (38,630,596) is unaffected by all value-side anomalies ✓.
- **Counts that update APPROACH.md:** distributor leading zeros → **9,382 rows (15.1 %)**;
  territory renames → **4,890 fact rows** + 1 `dim_geo` row (was "~190").
