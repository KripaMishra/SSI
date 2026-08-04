import json
import concurrent.futures

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, MessagesState, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.graph.state import CompiledStateGraph
from langchain_openai import ChatOpenAI

from src.agent.config import AgentConfig, agent_config
from src.agent.models import AgentResponse
from src.agent.tools import search_docs, describe_database, query_database
from src.agent.callbacks import DebugCallbackHandler
from src.utils.logger import get_logger

logger = get_logger(__name__)

AGENT_TIMEOUT = 180


class AgentTimeoutError(Exception):
    pass


try:
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    from dotenv import load_dotenv
    env_path = __import__("pathlib").Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(env_path)

    _langfuse = Langfuse()
    _langfuse_handler = CallbackHandler()
    logger.info("langfuse tracing initialized")
except Exception:
    _langfuse_handler = None
    logger.info("langfuse not configured, tracing disabled")


def _load_system_prompt() -> str:
    path = __import__("pathlib").Path(__file__).resolve().parent / "prompts" / "system.md"
    prompt = path.read_text(encoding="utf-8")
    logger.debug("loaded system prompt", extra={"length": len(prompt), "file": str(path)})
    return prompt


def build_agent(config: AgentConfig | None = None) -> CompiledStateGraph:
    if config is None:
        config = agent_config
    logger.info("building agent", extra={"model": config.model_name})

    tools = [search_docs, describe_database, query_database]

    llm = ChatOpenAI(
        model=config.model_name,
        base_url=config.openai_base_url,
        api_key=config.openai_api_key,
        temperature=0,
        reasoning_effort="low"
    )

    structured_llm = llm.with_structured_output(AgentResponse, method="json_mode")

    system_prompt = _load_system_prompt()

    def llm_call(state: MessagesState) -> dict:
        model_with_tools = llm.bind_tools(tools)
        response = model_with_tools.invoke(
            [{"role": "system", "content": system_prompt}] + state["messages"]
        )
        return {"messages": [response]}

    def finalize(state: MessagesState) -> dict:
        last = state["messages"][-1]
        raw = last.content if hasattr(last, "content") else str(last)
        try:
            schema = {
                "answer": "str — final answer text",
                "intent": "Literal['WHAT','WHY','WHAT_TO_DO','OUT_OF_DOMAIN']",
                "citations": "list[str] — source references; MUST be non-empty for WHY intent",
                "confidence": "float 0.0–1.0",
                "status": "Literal['OK','PENDING_APPROVAL','ABSTAINED','ERROR']",
            }
            validated: AgentResponse = structured_llm.invoke(
                [{"role": "system", "content": system_prompt}]
                + state["messages"]
                + [{"role": "user", "content": f"Reformat the above conversation into valid JSON. Use ONLY these exact fields:\n{json.dumps(schema, indent=2)}\n\nEnsure intent, status, citations, and confidence are all present and match the allowed values."}]
            )
            return {"messages": [{"role": "assistant", "content": validated.model_dump_json()}]}
        except Exception:
            logger.exception("structured output validation failed", extra={"raw": str(raw)[:300]})
            fallback = AgentResponse(
                answer=str(raw),
                intent="WHAT",
                citations=[],
                confidence=0.5,
                status="OK",
            )
            return {"messages": [{"role": "assistant", "content": fallback.model_dump_json()}]}

    tool_node = ToolNode(tools)

    def should_continue(state: MessagesState):
        last_message = state["messages"][-1]
        if getattr(last_message, "tool_calls", None):
            return "tool_node"
        return "finalize"

    builder = StateGraph(MessagesState)
    builder.add_node("llm_call", llm_call)
    builder.add_node("tool_node", tool_node)
    builder.add_node("finalize", finalize)
    builder.add_edge(START, "llm_call")
    builder.add_conditional_edges(
        "llm_call", should_continue, {"tool_node": "tool_node", "finalize": "finalize"}
    )
    builder.add_edge("tool_node", "llm_call")
    builder.add_edge("finalize", END)

    checkpointer = InMemorySaver()
    graph = builder.compile(checkpointer=checkpointer)
    return graph


def run_agent(question: str, config: AgentConfig | None = None) -> AgentResponse:
    logger.info("run_agent start", extra={"question": question[:200]})
    graph = build_agent(config)

    thread_config = {"configurable": {"thread_id": f"run_{id(question)}"}}
    callbacks = [_langfuse_handler] if _langfuse_handler else []
    callbacks.append(DebugCallbackHandler())

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            graph.invoke,
            {"messages": [{"role": "user", "content": question}]},
            {"configurable": thread_config["configurable"], "callbacks": callbacks},
        )
        try:
            result = future.result(timeout=AGENT_TIMEOUT)
        except concurrent.futures.TimeoutError:
            logger.error("agent invocation timed out", extra={"timeout": AGENT_TIMEOUT})
            raise AgentTimeoutError(f"Agent did not respond within {AGENT_TIMEOUT}s") from None

    last = result["messages"][-1]
    raw = last.content if hasattr(last, "content") else str(last)
    parsed = json.loads(raw)
    response = AgentResponse(**parsed)
    logger.info(
        "run_agent success",
        extra={
            "intent": response.intent,
            "confidence": response.confidence,
            "citations": len(response.citations),
        },
    )
    return response
