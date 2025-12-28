from fastapi import FastAPI

from src.auth.controller import router as auth_router


def register_routes(app: FastAPI):
    app.include_router(auth_router)
