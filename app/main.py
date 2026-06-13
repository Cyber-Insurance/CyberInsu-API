from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api import auth, admin, assureur, courtier, client


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db.database import engine, Base
    import app.db.models  # register all models with Base
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)

import os

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        os.getenv("FRONTEND_URL", "https://cyberinsu-front-end-production.up.railway.app"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(assureur.router)
app.include_router(courtier.router)
app.include_router(client.router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}
