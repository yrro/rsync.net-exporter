import enum
import os
from logging import INFO, DEBUG, basicConfig, getLogger, getLevelName


logger = getLogger(__name__)


class Host(enum.Enum):
    UNKNOWN = enum.auto()
    FLASK = enum.auto()
    GUNICORN = enum.auto()


def config_early() -> None:
    """
    Configure logging before anyone else has a chance. Try to obtain log level
    from our host environment.
    """

    gunicorn_logger = getLogger("gunicorn.error")
    if gunicorn_logger.handlers:
        host = Host.GUNICORN
        level = gunicorn_logger.level
    elif "FLASK_RUN_FROM_CLI" in os.environ:
        host = Host.FLASK
        if int(os.environ.get("FLASK_DEBUG", "0")):
            level = DEBUG
        else:
            level = INFO
    else:
        host = Host.UNKNOWN
        level = INFO

    basicConfig(level=level)

    if host == Host.UNKNOWN:
        logger.warning("Unknown host environment; defaulting log level to INFO")
    else:
        logger.debug(
            "Host environment: %s; log level: %s", host.name, getLevelName(level)
        )
