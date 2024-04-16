import enum
from logging import INFO, DEBUG, basicConfig, getLogger
import os
from typing import Final


LOGGER: Final = getLogger(__name__)


class Host(enum.Enum):

    UNKNOWN: Final = enum.auto()
    FLASK: Final = enum.auto()
    GUNICORN: Final = enum.auto()
    PYTEST: Final = enum.auto()

    @classmethod
    def detect(cls) -> "Host":
        if getLogger("gunicorn.error").handlers:
            return Host.GUNICORN
        if "FLASK_RUN_FROM_CLI" in os.environ:
            return Host.FLASK
        return Host.UNKNOWN

    def configure_logging(self) -> None:
        level = None

        if self == Host.FLASK:
            level = DEBUG if int(os.environ.get("FLASK_DEBUG", "0")) else INFO
        elif self == Host.GUNICORN:
            level = getLogger("gunicorn.error").level

        if level is not None:
            basicConfig(level=level)

        LOGGER.debug("Host environment: %s", self.name)
