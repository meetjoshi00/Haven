import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from apps.api.routers import coach, predict, alerts, coordinator
from apps.api.content import init_content_store
from apps.api.embeddings import get_embedding_model
from apps.api.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_settings().validate()
    app.state.content = init_content_store()
    get_embedding_model()
    coordinator.load_rules()
    yield


app = FastAPI(title="ASD Coaching API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("CORS_ORIGIN", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(coach.router,       prefix="/coach",       tags=["coach"])
app.include_router(predict.router,     prefix="/predict",     tags=["predict"])
app.include_router(alerts.router,      prefix="/alerts",      tags=["alerts"])
app.include_router(coordinator.router, prefix="/coordinator", tags=["coordinator"])


@app.get("/health")
async def health():
    return {"status": "ok"}
