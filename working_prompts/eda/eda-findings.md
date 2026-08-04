## 1. Dataset Overview



## 1.1 dim_distributor
- shape: (24, 3)
- duplicate rows: 0
- duplicate columns: []
- total nulls: 0
- dtypes:
distributor_id      str
distributor_name    str
territory           str


## 1.1 dim_geo
- shape: (12, 2)
- duplicate rows: 0
- duplicate columns: []
- total nulls: 0
- dtypes:
territory    str
region       str


## 1.1 dim_rep
- shape: (12, 3)
- duplicate rows: 0
- duplicate columns: []
- total nulls: 1
- dtypes:
rep_id       str
rep_name     str
territory    str


## 1.1 dim_sku
- shape: (136, 8)
- duplicate rows: 0
- duplicate columns: []
- total nulls: 0
- dtypes:
sku_code       str
category       str
brand          str
sku_name       str
pack_size      str
flavour        str
tier           str
base_mrp     int64


## 1.1 fact_primary_sales
- shape: (61955, 6)
- duplicate rows: 23
- duplicate columns: []
- total nulls: 2186
- dtypes:
week_start                 str
sku_code                   str
territory                  str
distributor_id             str
primary_sales_units    float64
primary_sales_value        str


## 1.1 fact_targets
- shape: (14292, 4)
- duplicate rows: 0
- duplicate columns: []
- total nulls: 0
- dtypes:
month               str
material_no         str
area                str
target_value    float64


## 1.1 promotions
- shape: (2, 5)
- duplicate rows: 0
- duplicate columns: []
- total nulls: 0
- dtypes:
week_start              str
sku                     str
territory               str
promo_type              str
promo_discount_pct    int64


## 1.1 stockouts
- shape: (2, 5)
- duplicate rows: 0
- duplicate columns: []
- total nulls: 0
- dtypes:
week_start         str
item_code          str
territory          str
stockout_flag    int64
stockout_days    int64


## 2. Cross-table structural checks



## 2.1 Shared column 'distributor_id'
present in: ['dim_distributor', 'fact_primary_sales']


## 2.1 Shared column 'sku_code'
present in: ['dim_sku', 'fact_primary_sales']


## 2.1 Shared column 'territory'
present in: ['dim_distributor', 'dim_geo', 'dim_rep', 'fact_primary_sales', 'promotions', 'stockouts']


## 2.1 Shared column 'week_start'
present in: ['fact_primary_sales', 'promotions', 'stockouts']


## 3. Categorical field analysis



## 3.dim_distributor.distributor_id
- distinct: 24
- sample values: ['DEL-D1', 'DEL-D2', 'LUC-D1', 'LUC-D2', 'JAI-D1', 'JAI-D2', 'MUM-D1', 'MUM-D2', 'PUN-D1', 'PUN-D2']


## 3.dim_distributor.distributor_name
- distinct: 24
- sample values: ['Delhi Distributors 1', 'Delhi Distributors 2', 'Lucknow Distributors 1', 'Lucknow Distributors 2', 'Jaipur Distributors 1', 'Jaipur Distributors 2', 'Mumbai Distributors 1', 'Mumbai Distributors 2', 'Pune Distributors 1', 'Pune Distributors 2']


## 3.dim_distributor.territory
- distinct: 12
- sample values: ['Delhi', 'Lucknow', 'Jaipur', 'Mumbai', 'Pune', 'Ahmedabad', 'Bengaluru', 'Chennai', 'Hyderabad', 'Kolkata']


## 3.dim_geo.territory
- distinct: 12
- sample values: ['Delhi', 'Lucknow', 'Jaipur', 'Bombay', 'Pune', 'Ahmedabad', 'Bengaluru', 'Chennai', 'Hyderabad', 'Kolkata']


## 3.dim_geo.region
- distinct: 5
- sample values: ['North', 'West', 'S', 'E', 'East']


## 3.dim_rep.rep_id
- distinct: 12
- sample values: ['SO-01', 'SO-02', 'SO-03', 'SO-04', 'SO-05', 'SO-06', 'SO-07', 'SO-08', 'SO-09', 'SO-10']


## 3.dim_rep.rep_name
- 1/12 missing (8.3%)
- distinct: 11
- sample values: ['Officer 1', 'Officer 2', 'Officer 3', 'Officer 5', 'Officer 6', 'Officer 7', 'Officer 8', 'Officer 9', 'Officer 10', 'Officer 11']


## 3.dim_rep.territory
- distinct: 12
- sample values: ['Delhi', 'Lucknow', 'Jaipur', 'Mumbai', 'Pune', 'Ahmedabad', 'Bengaluru', 'Chennai', 'Hyderabad', 'Kolkata']


## 3.dim_sku.sku_code
- distinct: 136
- CASE SENSITIVITY: values differ only by case → ['GJ-001', 'gj-001 ']
- CASE SENSITIVITY: values differ only by case → ['GJ-002', 'gj-002 ']
- WHITESPACE: 2 values have leading/trailing spaces
- sample values: ['GJ-001', 'GJ-002', 'GJ-003', 'GJ-004', 'GJ-005', 'GJ-006', 'GJ-007', 'GJ-008', 'GJ-009', 'CO-001']


## 3.dim_sku.category
- distinct: 5
- sample values: ['Biscuits', 'Tea', 'Detergent', 'Shampoo', 'Snacks']


## 3.dim_sku.brand
- distinct: 15
- sample values: ['GlucoJoy', 'CrunchO', 'NutriBite', 'ChaiRaja', 'MorningGold', 'TeaBliss', 'SparkClean', 'WashWell', 'PowerFoam', 'SilkNaturals']


## 3.dim_sku.sku_name
- distinct: 134
- sample values: ['GlucoJoy Original 50g', 'GlucoJoy Choco 50g', 'GlucoJoy Choco 120g', 'GlucoJoy ButterCookie 120g', 'GlucoJoy Original 200g', 'GlucoJoy Choco 200g', 'GlucoJoy Original 300g', 'GlucoJoy Choco 300g', 'GlucoJoy ButterCookie 300g', 'CrunchO Original 50g']


## 3.dim_sku.pack_size
- distinct: 15
- sample values: ['50g', '120g', '200g', '300g', '100g', '250g', '500g', '1kg', '2kg', '90ml']


## 3.dim_sku.flavour
- distinct: 15
- sample values: ['Original', 'Choco', 'ButterCookie', 'Regular', 'Elaichi', 'Ginger', 'Masala', 'LemonFresh', 'RosePower', 'AntiDandruff']


## 3.dim_sku.tier
- distinct: 8
- CASE SENSITIVITY: values differ only by case → ['mainstream', 'Mainstream']
- CASE SENSITIVITY: values differ only by case → ['premium', 'Premium']
- CASE SENSITIVITY: values differ only by case → ['value', 'Value']
- sample values: ['VAL', 'mainstream', 'premium', 'value', 'Mainstream', 'Premium', 'Value', 'PREM']


## 3.fact_primary_sales.sku_code
- distinct: 134
- sample values: ['CK-001', 'CK-002', 'CK-003', 'CK-004', 'CK-005', 'CK-006', 'CK-007', 'CK-008', 'CK-009', 'CK-010']


## 3.fact_primary_sales.territory
- distinct: 13
- sample values: ['Ahmedabad', 'Chennai', 'Delhi', 'Guwahati', 'Hyderabad', 'Jaipur', 'Kolkata', 'Patna', 'Pune', 'BLR']


## 3.fact_primary_sales.distributor_id
- distinct: 48
- sample values: ['AHM-D1', 'CHE-D2', '0DEL-D1', 'GUW-D2', 'HYD-D1', 'JAI-D2', 'KOL-D1', 'PAT-D2', 'PUN-D2', '0AHM-D1']


## 3.fact_targets.material_no
- distinct: 134
- sample values: ['CK-001', 'CK-002', 'CK-003', 'CK-004', 'CK-005', 'CK-006', 'CK-007', 'CK-008', 'CK-009', 'CK-010']


## 3.fact_targets.area
- distinct: 12
- sample values: ['Ahmedabad', 'Chennai', 'Delhi', 'Guwahati', 'Hyderabad', 'Jaipur', 'Kolkata', 'Patna', 'Pune', 'Bengaluru']


## 3.promotions.sku
- distinct: 2
- sample values: ['SC-004', 'GJ-003']


## 3.promotions.territory
- distinct: 2
- sample values: ['Mumbai', 'North']


## 3.promotions.promo_type
- distinct: 1
- sample values: ['PriceOff']


## 3.stockouts.item_code
- distinct: 2
- sample values: ['GJ-003', 'CO-004']


## 3.stockouts.territory
- distinct: 2
- sample values: ['Delhi', 'Chennai']


## 3.stockouts.stockout_flag
- distinct: 1
- sample values: [1]


## 4. Numerical field analysis



## 4.dim_sku.base_mrp
- range: [5.00, 250.00]
- mean=76.34, median=55.00
- top-5 values: [250, 250, 250, 250, 250]
- bottom-5 values: [5, 5, 5, 5, 5]


## 4.fact_primary_sales.primary_sales_units
- 2186/61955 missing (3.5%)
- range: [-9999.00, 9999.00]
- mean=775.37, median=579.00
- NEGATIVES: 735 values < 0
- top-5 values: [9999.0, 9999.0, 9999.0, 9999.0, 9999.0]
- bottom-5 values: [-9999.0, -1326.0, -1243.0, -1036.0, -996.0]


## 4.fact_primary_sales.primary_sales_value
- 9416 non-numeric values coerced to NaN
- range: [412.50, 72495.00]
- mean=24622.33, median=23321.25
- top-5 values: [72495.0, 72405.0, 72360.0, 72045.0, 72000.0]
- bottom-5 values: [412.5, 562.5, 2295.0, 2298.75, 2298.75]


## 4.fact_targets.target_value
- range: [9701.85, 351618.74]
- mean=109077.69, median=102609.49
- top-5 values: [351618.74, 347339.07, 337729.71, 334600.75, 330056.07]
- bottom-5 values: [9701.85, 9750.46, 9811.36, 9882.26, 9958.59]


## 4.promotions.promo_discount_pct
- range: [15.00, 20.00]
- mean=17.50, median=17.50
- top-5 values: [20, 15]
- bottom-5 values: [15, 20]


## 4.stockouts.stockout_days
- range: [4.00, 5.00]
- mean=4.50, median=4.50
- top-5 values: [5, 4]
- bottom-5 values: [4, 5]


## 5. Date field analysis



## 5.fact_primary_sales.week_start
- MULTIPLE DATE FORMATS: {'YYYY-MM-DD': 50983, 'MM/DD/YY': 3734, 'DD Mon YYYY': 3665, 'DD-MM-YYYY': 3573}
- 10972 values failed date parsing beyond NA count


## 5.fact_targets.month



## 5.promotions.week_start



## 5.stockouts.week_start



## 6. Referential integrity checks



## 6. FK
- FK VIOLATION (fact_primary_sales.territory → dim_geo.territory): 3 values in territory not found in territory. Examples: ['BLR', 'BGL', 'Mumbai']


## 6. FK
- FK VIOLATION (fact_primary_sales.distributor_id → dim_distributor.distributor_id): 24 values in distributor_id not found in distributor_id. Examples: ['0JAI-D2', '0GUW-D2', '0BEN-D2', '0LUC-D1', '0KOL-D1', '0HYD-D2', '0KOL-D2', '0DEL-D1', '0BEN-D1', '0LUC-D2']


## 6. FK
- FK VIOLATION (fact_targets.area → dim_geo.territory): 1 values in area not found in territory. Examples: ['Mumbai']


## 6. FK
- FK VIOLATION (promotions.territory → dim_geo.territory): 2 values in territory not found in territory. Examples: ['Mumbai', 'North']


## 6. FK
- FK VIOLATION (dim_rep.territory → dim_geo.territory): 1 values in territory not found in territory. Examples: ['Mumbai']


## 6. FK
- FK VIOLATION (dim_distributor.territory → dim_geo.territory): 1 values in territory not found in territory. Examples: ['Mumbai']


## 7. Logical duplicate analysis



## 7.fact_primary_sales
- 46 rows (0.1%) are duplicates on composite key ['week_start', 'sku_code', 'territory', 'distributor_id']


## 7.fact_targets
- No logical duplicates on ['month', 'material_no', 'area']


## 7.promotions
- No logical duplicates on ['week_start', 'sku', 'territory']


## 7.stockouts
- No logical duplicates on ['week_start', 'item_code', 'territory']


## 8. Case-sensitivity cross-table impact



## 9. Summary of flagged issues
See findings above for flagged fields requiring attention.
