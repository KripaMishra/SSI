# ADR-002: Star schema modelling and null-with-flag handling of sentinel/negative values

## Status

Accepted (implemented; see ARTEFACT.md).

## Context

Raw data consists of 8 CSV tables with substantial quality problems:
4 date formats in `week_start` (10,972 rows), non-numeric `"Rs 1,234"` sales values
(9,416 rows), `9999`/`-9999` sentinel units (772 rows), negative unit values
(734 rows), 23 duplicate-row pairs, inconsistent territory/distributor/SKU/region
codes, and a promotion row with an invalid territory. LIMITATION: negative values
could be misinterpreted as sales returns — but no returns dimension exists, so
subtracting them would corrupt gross-sales reconciliation. Limitation #2 in
APPROACH.md notes many anomalies lack documentation.

## Decision

1. **Star schema**: 4 dimension tables (`dim_geo`, `dim_sku`, `dim_rep`,
   `dim_distributor`) + 2 fact tables (`fact_primary_sales`, `fact_targets`) +
   2 supporting tables (`promotions`, `stockouts`), relationships enforced via FKs.
2. **Null with flags**: sentinel (`9999`, `-9999`) and negative values in
   `primary_sales_units` are nulled, *not* removed. Each affected row carries a
   `sales_units_flag` column (`sentinel_9999`, `sentinel_-9999`, `negative`, `ok`).
   The system prompt instructs the agent to treat `flag != "ok"` rows as
   unreliable, exclude them from quantitative conclusions, and mention the flag
   when quoting affected data.

## Consequences

- **Positive**: reconciliation is reproducible — the 52-week national total of
  38,630,596 units counts only `flag = "ok"` rows (60,426 of 61,932); bad values
  stay visible for audit instead of vanishing; returns can never be accidentally
  subtracted from gross sales.
- **Negative**: every downstream query must filter by flag (agent must remember);
  ~2.4% of unit rows (1,506) are excluded from quantitative answers; agents may
  still misread the flag without a strong prompt.

## Alternatives considered

- **Drop bad rows outright**: rejected — irreversible data loss, no audit trail.
- **Keep raw values and sanitize only at query time**: rejected — every aggregate
  and join would silently include sentinels/negatives.
- **Impute missing units**: rejected — fabricates data; undermines the causal
  analysis the system must support.
