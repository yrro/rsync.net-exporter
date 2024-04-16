from importlib import metadata
from typing import Final

from flask import Flask
from prometheus_flask_exporter import PrometheusMetrics  # type: ignore [import-untyped]

from . import (
    log_config,
    exporter,
)


def create_app(host: log_config.Host | None = None) -> Flask:
    if host is None:
        host = log_config.Host.detect()

    host.configure_logging()

    app: Final = Flask(__name__)

    app.config.from_object(f"{__name__}.default_settings")
    app.config.from_prefixed_env()

    app.register_blueprint(exporter.exporter)

    metrics: Final = PrometheusMetrics(app)
    metrics.info(
        "rsyncnet_exporter_info",
        "Information about rsync.net-exporter itself",
        version=metadata.version("rsync-net-exporter"),
    )

    return app
