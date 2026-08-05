# Approach

## Problem Summary

The objective is to create an assistant that answers What / Why / What-to-do questions over the provided structured and unstructured data. 

The PRD also provides two sample test queries : (1) "Why did SparkClean 1kg primary sales spike in Mumbai in the week of 16 Sep 2025?" (2) "What were GlucoJoy's monthly primary sales vs target in the North region in November 2025?"

The PRD also asks for a `multi-agent` system. 

The core components include 
1. Data interaction layer
2. Agent runtime loop 

<!-- Describe the problem you are solving and the key constraints. -->
## Technical Approach

0. Data cleaning csv: Inconsistencies found, and the approach taken to clean the structued data. 
1. Data modelling approach for structured data.
2. Mention the decision to keep the values such as -1, 9999 to deliberately, point out the fault data. Also ensure the agent prompt has this instruction to use the added flag in the csv data, and thus assuming that data is faulty and not sufficient to make a conclusion.
2. Text data cleaning approach. PII redaction, Chunking choice of 1 chunk per text file. 
3. Logic for extracting the metaadata and using it for filtering the data, to improve retrieval. 
4. Mounted retrieval tools  {numer of tools}
5. Using a sinlge agent architecture with data base querying tools, recusively calling the tools, added timeout to prevent infinite recursion. Better apporach should be implemented depeneding on the exact use-case, timeout to be reduced based on how we serve the api in production. 
6. using a message queue to handle high traffic. 
7. using semantic caching to reduce the LLM api calls. 
8. The current approach for the Cache invalidation is very naive as it only uses TTLs. A rather better versions would use invalidating on data updates. Better cache synthesis on the basis of frequent topics discussed --> pre-synthesised cache --> invalidated on data update. 
9. Mermaid diagram of the actual architecture, ERD of data modelling logic.
10. Langfuse for tracing. 

<!-- Outline your solution architecture, data pipeline, and implementation steps. -->
    
## AI Tool Usage
1. Usind OC as primary coding agent. 
2. Attached prompts used in working_prompts/
3. The token generation is very quick, but the harness itself is not to my liking. had to prompt to use the ctxMode extension instead of it discoving and using it by default. Also missing very basic checks such as not updating the dependencies, OC has LSP support inbuilt but it ignored a lot issues and only picked them when explicitly asked. Forgot to load the env vars while setting up the configs (very primitive error) 
4. The documentation lookup is efficient when explicitly mentioning the source doc. but adherence to it is still questionable, it ended up using a deprecated fucntionality from langGraph, that too.. after being flagged by the LSP. also ended up using manual json parsing instead of using direct structured response. fixed only on flagging.
5.  Very minor mishandling such as returning 200 status code on timeouts is wilddd. 
6. apart from These critiques, it is good at long running tasks when specified properly, so providing large chunks of tasks with step-by-step breakdown is efficient and managable.


<!-- Document how you used Cadra (OpenCode) during development — prompts, iterations, and what worked. -->

## Trade-offs & Limitations

1. Assumed the scope of the agent to be a stateless agent, with ability to query the database and reason over it to generate the responses, thus couldn't justify using a multi-agent system that would introduce a lot of complexity in terms of agent interactions, supervision, state-management, decision boundaries, excessive token consumption and higher latency. Effectively ended up using a single agent with tool loop.
2. A lot of inconsistencies in the dataset, sepcifically in sales numbers, better documentation/context of these  inconsistencies would have helped salvage some of thees data points, ateleast better handling [TBD]
3. The symantic cache is effective just in place to establish the methodology. A better approach would be handle the cache invalidation [mention the eact approach]
4. Latency is higher bcs we're using deepseek-v4-flash, definately an overkill for the objective and objectively slower, why use it then ? resource constraints on gemini-flash-lite. 
5. Using a read replica of the structured database could permit raw qery execution that could technically allow large and more complex queries to be run in one go, currently the query is wrapped in an ORM that limits the capabilities and thus leading to repeated tool calls. Ultimately a call on standards adhered by the company.
6. Lack of evals and prompt benchmarking.
7. The tracing is broken in vecel deployment would debug it if allowed by time. 
8. Had to rework the message-queuing from python-rq to qstash led to rework and refactors and thus burned through AI credits thus, couldn't run a any dedicated review loops via agent.

<!-- Note compromises, assumptions, and what you would improve with more time. -->



reference content from PRD is given below, it explains what to document in approach.md along with some pointers that i documented for the development and planning life-cycle use this to draft final version of approach.md  
```txt
Submit an approach document (max 2-3 pages) covering: Section A — Problem Decomposition: what analytical question types the solution should support and the specific structured output each should produce. Section B — Solution & Agentic Construct Design: the methods you chose and why, plus an explicit agentic construct — named steps with their inputs, outputs, handoffs, and failure paths. Section C — Data Interaction Design: how the system accesses the datasets, stays schema-aware, and performs aggregations (time grain, dimensional hierarchy, metric derivation). Section D — Risk Awareness & Trade-Off Reasoning: one risk each for incorrect query generation, hallucinated responses, and data misinterpretation — each with a concrete mitigation — and one explicit design trade-off you made
```
