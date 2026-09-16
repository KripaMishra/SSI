from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    actor: str
    queue: str
    attempts: int
    created_at: float | None = None
    started_at: float | None = None
    finished_at: float | None = None
    result: dict | None = None
    error: str | None = None


class ErrorResponse(BaseModel):
    detail: str
