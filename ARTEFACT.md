# Reconciliation Report

## National 52-Week Primary Sales Total

**38,630,596 units** (across all territories, all SKUs, 52 weeks — Jul 2025 – Jun 2026)

This figure includes only rows flagged `sales_units_flag = "ok"` (60,426 out of 61,932 total rows). Excluded: 1,506 rows with nulled sentinel/negative values (see below).

---

## Top-3 Data-Quality Fixes (by Rows Affected)

| Rank | Fix | Rows Affected | Detail |
|---|---|---|---|
| 1 | **Date format normalization** | 10,972 | `week_start` had 4 formats: `YYYY-MM-DD`, `DD-MM-YYYY`, `MM/DD/YY`, `DD Mon YYYY` — all normalized to `YYYY-MM-DD` |
| 2 | **Non-numeric sales value extraction** | 9,416 | `primary_sales_value` contained `"Rs 1,234"` string patterns — extracted numeric portion (stripped `"Rs "` prefix and commas) |
| 3 | **Sentinel & negative value nullification** | 1,506 | 771 × `9999` → NULL (sentinel), 734 × negative values → NULL (data errors), 1 × `-9999` → NULL (sentinel). Each row flagged with `sales_units_flag` for downstream confidence adjustment |

---

## Returns / Unit-Mixing Rule

Negative values in `primary_sales_units` are treated as **data quality issues, not sales returns**. The dataset has no separate returns dimension or credit note table. All 734 negative values were nulled and flagged `sales_units_flag = "negative"`. The agent is instructed via system prompt to:

- Treat rows with `sales_units_flag != "ok"` as unreliable
- Not use them in quantitative conclusions
- Mention the flag when quoting affected data

This prevents returns from being accidentally subtracted from gross sales. If actual returns data exists in the future, it should be modelled as a separate fact table.

---

## Records Excluded

| Exclusion | Count | Reason | Stored At |
|---|---|---|---|
| Duplicate sales rows | 23 rows | Exact matches on composite key `(week_start, sku_code, territory, distributor_id)` — kept first instance | `omitted/fact_primary_sales_duplicates.csv` |
| Promotion with `territory = "North"` | 1 row | `"North"` is a region code, not a valid territory — FK violation to `dim_geo` | `omitted/promotions_north_territory.csv` |
| PII from text documents | 12 redactions | 4 names, 4 emails, 4 phones redacted from 30 `.txt` files (emails, notes, circulars) | Redacted in-place in `cleaned/cleaned_docs.jsonl` |

### PII Redaction Details

| PII Type | Pattern | Redactions |
|---|---|---|
| Phone | `+91XXXXXXXXXX` | 4 |
| Email | `name@domain.com` | 4 |
| Name | `From:` header + verb-context (spoke, said, reported, etc.) | 4 |

Redacted values replaced with `<REDACTED_PHONE>`, `<REDACTED_EMAIL>`, `<REDACTED_NAME>`. Original plain-text files remain in `Data/docs/` and should be access-controlled separately.

---

## Assumptions

1. Nulled `primary_sales_units` (sentinel/negative rows) are excluded from the reconciled total — they are flagged but not counted.
2. `primary_sales_value` was not used in unit reconciliation; it tracks monetary value only.
3. The 23 duplicate rows are exact copies — no meaningful data is lost by dropping one instance per pair.
4. The 52-week window runs from `2025-07-01` to `2026-06-23` (last full week of data at ingestion).
