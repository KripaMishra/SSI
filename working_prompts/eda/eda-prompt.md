perform eda on /home/kripa/Personal/projects/SSI/Data/*.csv, use python+pandas script to explore the data, 
we're looking for data inconsistencies in numerical and categorical fields such as duplicates, na, malformed values for categorical features, inconsistent date-formats as in Data/fact_primary_sales.csvm, case senstivity, and any other anomalies in numerical/categorical features. 

DONT LOAD the whole data into context, scripts only. keep a .md file for documenting the findings and flagging the fields. 
Continue only if you understand the scope and objective of the task, other wise use /grill-me skill


-----
i've update the path to the script, scripts/eda_script.py 
The actaul data in Data/ is available only for the read access. we maintain a cleaned dir for the ingestion copy(pre-processed) and maintain a omitted for the ones being sliced off(with reason, why removed. from working copy)
next step is to map the pre-processing steps to the respectives files. 
1. primary_sales_value mixed types :  check the different patterns used in the strings values and add a step to extract the exact numerical value. This should be evidence driven meaning after you're sure you've captured all the variants of strings values, and doucmented them, then only add the preprocessing step for it. 
2. primary_sales_units negatives: for preprocessing, we need to add a flag to these rows so they don't affect the aggregation pipelines. The flags would be used to filter them out. We dont remove these values bcs we need to report the malformed or inaccurate data in retrieval process that will be used in downstream process later. 
3. fact_primary_sales.week_start: normalize to YYYY-MM-DD as processing step. 
4. distributor_id FK violation : Clean these 
5. territory FK violations : add a mapping to make it mumbai, BLR is Bengaluru, and add bengal in geo. Need to map these to appropriate fields. 
6.dim_sku.tier case : Map these to lower case values. and check the variants for casese `VAL/PREM — 3 case variants + 2 abbreviations` and also map them to the standardized values (you decide the value that is consistent with the rest of the category norm of that feature)
7. dim_sku.sku_code whitespace: clean these. 
8.dim_geo.region: use the full names. map the abbreviations to repective values. 
8. dim_geo vs rest: Map to Mumbai. 
9. dim_rep.rep_name : Add the missing rep_name base it it on rep_id. 
10.fact_primary_sales duplicates : add them to the ommitted slice of the dataset.
11. promotions.territory: move to omitted sliced version
