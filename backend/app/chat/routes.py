from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.chat.schemas import ChatRequest
from rag_core.rag.generation import stream_rag_answer
from rag_core.rag.schemas import ChatQuery, ChatTurn as RagChatTurn

router = APIRouter()


@router.post("/chat")
async def chat(request: ChatRequest):
    query = ChatQuery(
        input=request.input,
        history=[
            RagChatTurn(input=turn.input, response=turn.response)
            for turn in request.history
        ],
    )

    async def generate():
        async for chunk in stream_rag_answer(query):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")
