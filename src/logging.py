import logging
from enum import StrEnum

LOG_FORMAT_DEBUG = (
    "%(levelname)s:%(message)s:%(pathname)s:%(funcName)s:%(lineno)d"
)


class LogLevels(StrEnum):
    info = "INFO"
    warn = "WARNING"
    error = "ERROR"
    debug = "DEBUG"


def configure_logging(log_level: LogLevels = LogLevels.error) -> None:
    """
    Configure application-wide logging.

    Must be called once at startup.
    """

    level_name = log_level.value  # guaranteed valid string for logging

    logging.basicConfig(
        level=level_name,
        format=LOG_FORMAT_DEBUG if log_level is LogLevels.debug else None,
    )
