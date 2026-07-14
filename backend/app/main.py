from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.chat.routes import router as chat_router
from app.home.routes import router as home_router
from app.upload.routes import router as upload_router


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
)

app.include_router(home_router)
app.include_router(chat_router)
app.include_router(upload_router)
