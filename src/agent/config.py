from pydantic_settings import BaseSettings


class AgentConfig(BaseSettings):
    # Command Code Provider API (OpenAI-compatible). Key from Studio -> API keys.
    openai_base_url: str = "https://api.commandcode.ai/provider/v1"
    openai_api_key: str = ""
    model_name: str = "deepseek/deepseek-v4-flash"
    # Must be one of the reasoning efforts the chosen model advertises
    # (deepseek/deepseek-v4-flash: "high" or "max").
    reasoning_effort: str = "high"
    search_top_k: int = 5


    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


agent_config = AgentConfig()
