from importlib import metadata

from flask import Flask
from prometheus_flask_exporter import PrometheusMetrics  # type: ignore [import-untyped]

from . import (
    log_config,
    exporter,
)


def create_app() -> Flask:
    log_config.config_early()

    app = Flask(__name__)
    app.register_blueprint(exporter.exporter)

    metrics = PrometheusMetrics(app)
    metrics.info(
        "rsyncnet_exporter_info",
        "Information about rsync.net-exporter itself",
        version=metadata.version("rsync-net-exporter"),
    )

    return app
