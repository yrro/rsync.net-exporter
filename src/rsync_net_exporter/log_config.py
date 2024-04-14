import enum
from logging import INFO, DEBUG, basicConfig, getLogger, getLevelName
import os


logger = getLogger(__name__)


class Host(enum.Enum):

    UNKNOWN = enum.auto()
    FLASK = enum.auto()
    GUNICORN = enum.auto()
    PYTEST = enum.auto()

    @classmethod
    def detect(cls) -> "Host":
        if getLogger("gunicorn.error").handlers:
            return Host.GUNICORN
        elif "FLASK_RUN_FROM_CLI" in os.environ:
            return Host.FLASK
        else:
            return Host.UNKNOWN


def config_early(host: Host | None = None) -> None:
    """
    Configure logging before anyone else has a chance. Try to obtain log level
    from our host environment.
    """

    host = host if host else Host.detect()

    if host == Host.GUNICORN:
        level = getLogger("gunicorn.error").level
    elif host == Host.FLASK:
        if int(os.environ.get("FLASK_DEBUG", "0")):
            level = DEBUG
        else:
            level = INFO
    elif host == Host.PYTEST:
        level = None
    elif host == Host.UNKNOWN:
        level = INFO

    if level is not None:
        basicConfig(level=level)

    if host == Host.UNKNOWN:
        logger.warning("Unknown host environment; defaulting log level to INFO")
    else:
        logger.debug(
            "Host environment: %s; log level: %s", host.name, getLevelName(level)
        )
