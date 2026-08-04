from typing import Literal
from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    answer: str = Field(description="Final answer to the user's question")
    intent: Literal["WHAT", "WHY", "WHAT_TO_DO", "OUT_OF_DOMAIN", "ERROR"] = Field(
        description="Intent classification of the question"
    )
    citations: list[str] = Field(
        description="Source references grounding the answer. MUST be non-empty for WHY intent."
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    status: Literal["OK", "PENDING_APPROVAL", "ABSTAINED", "ERROR"] = Field(
        description=(
            "OK = final answer ready. "
            "PENDING_APPROVAL = recommendation (WHAT_TO_DO) needs human approval. "
            "ABSTAINED = question unanswerable from available data. "
            "ERROR = agent execution failed."
        )
    )