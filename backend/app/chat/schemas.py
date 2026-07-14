from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    input: str
    response: str


class ChatRequest(BaseModel):
    input: str
    history: list[ChatTurn] = Field(default_factory=list)
