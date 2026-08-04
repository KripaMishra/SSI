from langchain_core.callbacks import BaseCallbackHandler
from src.utils.logger import get_logger

logger = get_logger(__name__)


class DebugCallbackHandler(BaseCallbackHandler):
    def on_llm_start(self, serialized, prompts, **kwargs):
        logger.debug("LLM call start", extra={"prompt_preview": prompts[0][:200] if prompts else ""})

    def on_llm_end(self, response, **kwargs):
        gen = response.generations[0][0]
        text = gen.text
        if hasattr(gen, "message") and gen.message:
            msg = gen.message
            if msg.tool_calls:
                tcs = [{ "name": tc["name"], "args": tc["args"] } for tc in msg.tool_calls]
                logger.debug("LLM response (tool calls)",
                             extra={"tool_calls": tcs, "text_preview": text[:300]})
            else:
                logger.debug("LLM response (text)", extra={"text_preview": text[:500]})
        else:
            logger.debug("LLM response", extra={"text_preview": text[:500]})

    def on_llm_error(self, error, **kwargs):
        logger.exception("LLM call error", extra={"error": str(error)[:300]})

    def on_tool_start(self, serialized, input_str, **kwargs):
        name = serialized.get("name", "unknown")
        logger.debug("tool start", extra={"tool": name, "input": input_str[:300]})

    def on_tool_end(self, output, **kwargs):
        logger.debug("tool end", extra={"output_preview": str(output)[:300]})

    def on_tool_error(self, error, **kwargs):
        logger.exception("tool error", extra={"error": str(error)[:300]})

    def on_chain_start(self, serialized, inputs, **kwargs):
        logger.debug("chain/agent step start")

    def on_chain_end(self, outputs, **kwargs):
        logger.debug("chain/agent step end")