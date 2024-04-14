import enum
from logging import INFO, DEBUG, basicConfig, getLogger
import os
from typing import Optional


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
        if "FLASK_RUN_FROM_CLI" in os.environ:
            return Host.FLASK
        return Host.UNKNOWN

    def get_level(self) -> Optional[int]:
        if self == Host.UNKNOWN:
            return INFO
        if self == Host.FLASK:
            return DEBUG if int(os.environ.get("FLASK_DEBUG", "0")) else INFO
        if self == Host.GUNICORN:
            return getLogger("gunicorn.error").level
        return None


def config_early(host: Optional[Host] = None) -> None:
    """
    Configure logging before anyone else has a chance. Try to obtain log level
    from our host environment.
    """

    if host is None:
        host = Host.detect()

    if level := host.get_level():
        basicConfig(level=level)

    logger.debug("Host environment: %s", host.name)
