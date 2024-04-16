from urllib.parse import urlsplit
from typing import Final

from flask import Blueprint, current_app, request
from flask.typing import ResponseReturnValue
import prometheus_client

from . import collector


exporter: Final = Blueprint("exporter", __name__)  # pylint: disable=invalid-name


@exporter.route("/probe")
def probe() -> ResponseReturnValue:
    if not (target := request.args.get("target")):
        return "Missing parameter: 'target'", 400

    netloc: Final = urlsplit(target).netloc
    netloc_t: Final = netloc.partition(":")
    if netloc_t[0] != current_app.config["RSYNC_NET_HOST"]:
        return "'target' points to forbidden host", 403

    col: Final = collector.Collector(target)

    reg: Final = prometheus_client.CollectorRegistry()
    reg.register(col)
    return prometheus_client.make_wsgi_app(reg)
