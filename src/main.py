import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api import register_routes
from src.database.mongo import close_mongodb_connection
from src.rate_limiting import limiter

from .logging import LogLevels, configure_logging

configure_logging(LogLevels.info)

logger = logging.getLogger(__name__)


async def _check_postgres() -> bool:
    """Ping PostgreSQL with a simple SELECT 1 query."""
    from sqlalchemy import text
    from src.database.core import engine
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"PostgreSQL health check FAILED: {e}")
        return False


async def _check_mongodb() -> bool:
    """Ping MongoDB with admin.command('ping')."""
    from src.database.mongo import client
    try:
        await client.admin.command("ping")
        return True
    except Exception as e:
        logger.error(f"MongoDB health check FAILED: {e}")
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup health checks ──
    logger.info("🔍 Running startup health checks...")

    pg_ok = await _check_postgres()
    mongo_ok = await _check_mongodb()

    if pg_ok:
        logger.info("PostgreSQL (Supabase) — connected")
    else:
        logger.critical("PostgreSQL (Supabase) — UNREACHABLE. Exiting.")
        sys.exit(1)

    if mongo_ok:
        logger.info("MongoDB — connected")
    else:
        logger.warning("MongoDB — UNREACHABLE. Chat/analysis features will fail.")

    logger.info("Everything Ready...")
    yield

    await close_mongodb_connection()
    logger.info("Closed connections...")

app = FastAPI(lifespan=lifespan)

# CORS Configuration - Allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

register_routes(app)
