from importlib import metadata
from typing import Optional

from flask import Flask
from prometheus_flask_exporter import PrometheusMetrics  # type: ignore [import-untyped]

from . import (
    log_config,
    exporter,
)


def create_app(host: Optional[log_config.Host] = None) -> Flask:
    log_config.config_early(host)

    app = Flask(__name__)

    app.config.from_object(f"{__name__}.default_settings")
    app.config.from_prefixed_env()

    app.register_blueprint(exporter.exporter)

    metrics = PrometheusMetrics(app)
    metrics.info(
        "rsyncnet_exporter_info",
        "Information about rsync.net-exporter itself",
        version=metadata.version("rsync-net-exporter"),
    )

    return app
