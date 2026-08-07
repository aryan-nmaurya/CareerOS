from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from db.base import Base
from db.session import engine
from models import user as _user_models  # noqa: F401  registers tables on Base
from routers import health


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

    app.include_router(health.router)
    return app


app = create_app()
