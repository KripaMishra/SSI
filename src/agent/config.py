from pydantic_settings import BaseSettings


class AgentConfig(BaseSettings):
    openai_base_url: str = "http://localhost:8521/v1"
    openai_api_key: str = ""
    model_name: str = "deepseek-v4-flash"
    search_top_k: int = 5


    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


agent_config = AgentConfig()
