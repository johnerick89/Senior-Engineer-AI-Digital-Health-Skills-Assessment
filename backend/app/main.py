from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chats import router as chats_router
from app.api.documents import router as documents_router
from app.api.home import api_router as home_api_router
from app.api.home import root_router as home_root_router
from app.api.usage import router as usage_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Ensure pgvector schema exists when the API starts."""
    try:
        from rag_core.rag.vector_store import initialize_vector_store

        initialize_vector_store()
    except Exception:
        # Allow the app to boot; upload will fail clearly if DB is unreachable.
        import logging

        logging.getLogger(__name__).exception("vector_store_init_failed")
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Chat-Id", "X-Chat-Title"],
)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(home_api_router)
api_v1.include_router(chats_router)
api_v1.include_router(documents_router)
api_v1.include_router(usage_router)

app.include_router(home_root_router)
app.include_router(api_v1)
