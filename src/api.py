from fastapi import FastAPI

from src.ai.controller import router as ai_router
from src.assignments.controller import router as assignments_router
from src.auth.controller import router as auth_router
from src.cases.controller import router as cases_router
from src.reports.controller import router as reports_router
from src.users.controller import router as user_router


def register_routes(app: FastAPI):
    app.include_router(auth_router)
    app.include_router(user_router)
    app.include_router(assignments_router)
    app.include_router(cases_router)
    app.include_router(reports_router)
    app.include_router(ai_router)
