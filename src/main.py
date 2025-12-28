from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from src.api import register_routes
from src.rate_limiting import limiter

from .logging import LogLevels, configure_logging

configure_logging(LogLevels.info)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

register_routes(app)
