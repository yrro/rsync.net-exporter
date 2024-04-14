from urllib.parse import urlsplit

from flask import Blueprint, current_app, request
from flask.typing import ResponseReturnValue
import prometheus_client

from . import collector


exporter = Blueprint("exporter", __name__)


@exporter.route("/probe")
def probe() -> ResponseReturnValue:
    if not (target := request.args.get("target")):
        return "Missing parameter: 'target'", 400

    netloc = urlsplit(target).netloc
    host, sep, port = netloc.partition(":")  # pylint: disable=unused-variable
    if host != current_app.config["RSYNC_NET_HOST"]:
        return "'target' points to forbidden host", 403

    col = collector.Collector(target)

    reg = prometheus_client.CollectorRegistry()
    reg.register(col)
    return prometheus_client.make_wsgi_app(reg)
