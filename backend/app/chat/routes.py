import asyncio

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.chat.schemas import ChatRequest

router = APIRouter()


async def stream_echo_response(text: str):
    response = f'You said "{text}"'
    chunk_size = 4
    for i in range(0, len(response), chunk_size):
        yield response[i : i + chunk_size]
        await asyncio.sleep(0.02)


@router.post("/chat")
async def chat(request: ChatRequest):
    async def generate():
        async for chunk in stream_echo_response(request.input):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")
