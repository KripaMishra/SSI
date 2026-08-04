"""Evidence-driven analysis: primary_sales_value string patterns."""
import pandas as pd
import re

df = pd.read_csv('Data/fact_primary_sales.csv', dtype=str)
vals = df['primary_sales_value'].dropna().astype(str).str.strip()

numeric_mask = vals.str.match(r'^-?\d+(\.\d+)?$')
non_numeric = vals[~numeric_mask]
numeric = vals[numeric_mask]

patterns = {}
for v in non_numeric.unique():
    v_str = str(v)
    nums = re.findall(r'[-+]?\d+\.?\d*', v_str)
    wrapper = v_str
    for n in nums:
        wrapper = wrapper.replace(str(n), '{NUM}', 1)
    patterns[wrapper] = {
        'example': v_str,
        'count': int((non_numeric == v_str).sum()),
        'extracted_num': nums[0] if nums else None,
    }

print(f"Total rows: {len(df)}")
print(f"Purely numeric: {len(numeric)} ({len(numeric)/len(df)*100:.1f}%)")
print(f"Non-numeric strings: {len(non_numeric)} ({len(non_numeric)/len(df)*100:.1f}%)")
print(f"Unique string patterns: {len(patterns)}\n")

i = 0
for p, info in sorted(patterns.items(), key=lambda x: -x[1]['count']):
    i += 1
    pct = info['count'] / len(non_numeric) * 100
    print(f"  #{i:2d}  {info['count']:>5} rows ({pct:5.1f}%)  wrapper: {p!r:50s}")
    print(f"       example: {info['example']!r:30s}  extract: {info['extracted_num']}")
print()

# Also check if any purely numeric values have leading zeros / special formats
leading_zero = numeric.str.match(r'^0\d')
if leading_zero.any():
    print(f"Also: {leading_zero.sum()} numeric values have leading zeros (may be codes, not values)")
else:
    print("No numeric values with leading zeros.")