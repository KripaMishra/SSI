1. write a script to generate embeddings for the text part of the content in the JSONL: /home/kripa/Personal/projects/SSI/cleaned/cleaned_docs.jsonl
2. Use gemini embeddings 2 for model, here is the documentation https://ai.google.dev/gemini-api/docs/embeddings, model = gemini-embedding-2, dims = 1536. save the expanded version of cleand_docs.jsonl with embeddings in another jsonl file, called embeddings.jsonl
3. a pipeline/ingest.py that ingests the embeddings to a chroma db client.[updte the env.exaple, i'll populate the .env] from the jsonl file. it will have an embedding field with resto of the fields as metadata, we want to keep the metadata that will be used for search filetering, https://docs.trychroma.com/docs/overview/getting-started

Final outcome: properly setup script for embedding generation and data ingestions, both separate files.
Keep configs separate, don't mix with pipeline files. use the pydantic settings to load. use these standard practices in this project. 
the scripts must use arg parse argumests to either ingest or qeury the data such as {file}.py ingest 
or {file}.py query "what do we know about glucoJoy"


-----
Generating and ingesting the embeddings:
```python
import chromadb

client = chromadb.CloudClient(
  api_key='YOUR_API_KEY',
  tenant='tenant_id',
  database='test'
)```  
use this snippet as reference, update the client configuration, and run the embedding and ingestion pipeline. 

Keep the client modular, we will query function as tool that can be mounted to the agent, check agent implmementation task for further reference.
