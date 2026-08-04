# Agent implementation Spec
1. Framework: Langgraph
2. single agent loop until final respnose. multiple read tools
3. no memory, no checkpointing, no conversation history, sessions etc, simple stateless agent loop. 
4. openai compatible backend using opencode-go : https://opencode.ai/docs/go/ documentation for backend.
5. maintain the config in config file. including the reasoning effort and model names, also keep the OpenAIbase url as a config, that can be loaded from the env. 
6. tools : 
  1. search_docs(description= "searches the vector database, pass params such as top_k as config a parameter in tool call, it has a defult value but agent and adjust")
  2. describe_database(description= "returns available relational databases, columns and types + relationships.") reference/home/kripa/Personal/projects/SSI/Data/DATA_DICTIONARY.md
  3. query_database(description= query the relational database) note the tools is read only, the functionality needs to implemented in db/ and will be imported and mounted in teh agent/tools
  4. Each tool response can be used for citation thus must include the citation string references, Your task is to define this reference format. Considerations 1. we have 2 dbs, one relational and one vector. must capture the granularity of both without being hardwired for just either one ==> need to be modular.
7. Response format: the agent returns a structured response, here is the reference:
     ```reference 
    a `POST /ask` endpoint. Request body: `{"question": "..."}`. Response body: `{"answer": string, "intent": "WHAT" | "WHY" | "WHAT_TO_DO" | "OUT_OF_DOMAIN", "citations": string[], "confidence": number, "status": "OK" | "PENDING_APPROVAL" | "ABSTAINED"}`. Rules: any recommendation (`intent: WHAT_TO_DO`) must return `status: PENDING_APPROVAL` — a recommendation is never returned as final `status: OK`, it always requires human approval before being treated as actioned. Any question that is unanswerable from the provided data or rests on a false premise must return `status: ABSTAINED` rather than a fabricated answer. Any `WHY` answer must carry a non-empty `citations` array grounding the explanation in the underlying data. ```
  Define one pydantic model for response that get's used in the fastAPI /ask for response validation and also get's passed on to the agent for resposne_schema in configuration, check out the openAi comptible format for more references. 
8. An initial prompt for the agent, explaining the role. and data usage, keep it in a sprate folder. 
9. some of the reference: https://docs.langchain.com/oss/python/langchain/agents, https://docs.langchain.com/oss/python/langgraph/overview, https://docs.langchain.com/oss/python/langchain/tools , https://docs.langchain.com/oss/python/langchain/structured-output index the content of these using ctxmode and then query accordingly. 
10. Deliverables: agnet loop with tools, prompt, fastAPI endpoint /ask,


--------------
Bugs:
1. the respons is adding citations in answer field. that is incorrect, it should be in the response.citation field. 
2. the confidence is hardcoded based on the scenarios, that is incorrect. let ai generate it based on the available evidence. update the prompt. 
3.  P0, the bug```json
{"answer":"Primary sales for SparkClean 1kg spiked in Mumbai in the week of 16 Sep 2025 due to a **15% price-off promotion** introduced in that territory during that week.\n\n**Citations:**\n- Trade Circular: [vector_db:SSI:promo_circular_01]\n- Promotions Table: [relational_db:PROMOTIONS]\n- Primary Sales Table: [relational_db:FACT_PRIMARY_SALES]","intent":"WHAT","citations":[],"confidence":0.5,"status":"OK"}``` the citations need to be clean array of texts `"citations": string[]` supporting logs:
```json
{"timestamp": "2026-08-04T20:00:53", "level": "WARNING", "script": "/home/kripa/Personal/projects/SSI/agent/graph.py", "line": 70, "message": "agent response not JSON, wrapping as text", "extra": {"raw_start": "For November 2025, GlucoJoy's primary sales vs. target in the North region (territories: Delhi, Lucknow, Jaipur) were as follows:\n\n- **Primary Sales Value:** 861,938.25\n- **Primary Sales Units:** 83,1"}}

```
4.  P1 : Restructure the dirs : move agent and api, intern into the src/
5. [p1]move ssi.db into the internal/db, also update the script for generating the .db to put it in the db part only after moving the internal to src/ 
6.  P0 ```json
{"timestamp": "2026-08-04T20:00:51", "level": "INFO", "script": "/home/kripa/Personal/projects/SSI/agent/tools.py", "line": 72, "message": "tool:query_database", "extra": {"query": "SELECT \n    SUM(t.target_value) AS total_target_value\nFROM fact_targets t\nJOIN dim_geo g ON t.area = g.territory\nWHERE g.region = 'North'\n  AND t.material_no IN ('GJ-001', 'GJ-002', 'GJ-003', 'GJ-004'"}}``` We need to use orm for queries, not a direct raw query.
---- 
### Fixing the state
1. We need an in memory sesesion history for each run, this will allow the LLM to retain the context for previous tool calls, and enable it gather data via tool calls recursively. Update the graph, we'll also need a tool node and edges and a simple agent state defination, with start and end. use the stategraph from langGrph+ in memory session history.  https://docs.langchain.com/oss/python/langgraph/add-memory#add-short-term-memory, https://docs.langchain.com/oss/python/langgraph/quickstart#2-define-state, use ctx mode
2. Check if we're properly using the structured response generation, shouldn't we be using structured response in this initialization for final response ?
```py
def build_agent(config: AgentConfig | None = None):
    if config is None:
        config = agent_config
    logger.info("building agent", extra={"model": config.model_name})

    tools = [search_docs, describe_database, query_database]

    llm = ChatGoogleGenerativeAI(
        model=config.model_name,
        api_key=config.effective_gemini_key,
        temperature=0,
    )

    agent = create_agent(llm, tools, system_prompt=_load_system_prompt() )
    return agent
```
---- 
### Semantic Caching and Queuing

3. add a redis based message-queue for serving the /ask endpoint. 5 concurrent requests at a time. the limit will be a configurable env var that defaults to 5.
4. implement a basic redis based semantic caching, where we store the last successfull query and response embeddings(re-use current embedding generation pipeline). and if the incoming query is 97% or more similar we return the same result right away. for now each cache can have ttl of 10 mins. after invalidation, the very next response get's cached, completing the cache life-cycle.
  4.1. start with the test cases, for cache match vs cache miss. 10 cases at least. covering the different range of queries. 
5. create a docker-compose with our fastAPI service and a redis instance and it will be used by the cache component in the SSI service and rq worker. 3 working as a seprate services Properly handle the bridge network config
6. Ensure the requirements.txt is updated.
final flow is request--> cache matching --> if no matching--> queue--> agent--> return response.
