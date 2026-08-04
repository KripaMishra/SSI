1. Checkout the datasets at cleaned/*.csv [headings and metadata info using pandas] and analyze the tables, + columns. Objective: Model the PK and FK relations. 
2. Use a postgresql as primary and local sql db as fallback db. ingest these into the database. 
3. Use an orm, no  direct SQL query. 
4. Add Ingestion pipeline script. 
NOTE: No inplace modification in the csv files. they're read only. 
Final Output

scripts for client initialization,setup and ingestion. 
a locally setup sqllite db. 
updated requirements 
updated .env.example for db config.
