from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ai.errors import AIInvalidResponse, AIUnavailable
from config import settings
from db.base import Base
from db.session import engine
from models import assessment as _assessment_models  # noqa: F401
from models import roadmap as _roadmap_models  # noqa: F401
from models import user as _user_models  # noqa: F401
from routers import assessment, health, profile, roadmap, tracks


def create_app() -> FastAPI:
    app = FastAPI(title="CareerOS API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    Base.metadata.create_all(bind=engine)

    @app.exception_handler(AIUnavailable)
    def handle_ai_unavailable(request, exc: AIUnavailable):
        return JSONResponse(
            status_code=503,
            content={"detail": {"code": "ai_unavailable", "message": str(exc)}},
        )

    @app.exception_handler(AIInvalidResponse)
    def handle_ai_invalid_response(request, exc: AIInvalidResponse):
        return JSONResponse(
            status_code=502,
            content={"detail": {"code": "ai_invalid_response", "message": str(exc)}},
        )

    app.include_router(health.router)
    app.include_router(profile.router)
    app.include_router(tracks.router)
    app.include_router(assessment.router)
    app.include_router(roadmap.router)
    return app


app = create_app()
