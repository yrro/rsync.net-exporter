from logging import getLogger
from typing import Iterator
import xml.etree.ElementTree as ET

from flask import Blueprint, request
from flask.typing import ResponseReturnValue
import prometheus_client
from prometheus_client.core import (
    CounterMetricFamily,
    GaugeMetricFamily,
    InfoMetricFamily,
)
import requests


logger = getLogger(__name__)

exporter = Blueprint("exporter", __name__)


@exporter.route("/probe")
def probe() -> ResponseReturnValue:

    if not (target := request.args.get("target")):
        return "Missing parameter: 'target'", 400

    collector = Collector(target)

    reg = prometheus_client.CollectorRegistry()
    reg.register(collector)
    return prometheus_client.make_wsgi_app(reg)


class Collector(prometheus_client.registry.Collector):

    def __init__(self, target: str) -> None:
        self.__target = target
        self.__labelnames = ["uid", "nickname", "location"]
        self.__mf_quota = GaugeMetricFamily(
            "rsyncnet_account_quota_bytes", "Account quota", labels=self.__labelnames
        )
        self.__mf_billed = GaugeMetricFamily(
            "rsyncnet_account_billed_bytes",
            "Amount of quota-consuming data (including custom snapshots)",
            labels=self.__labelnames,
        )
        self.__mf_dataset = GaugeMetricFamily(
            "rsyncnet_account_dataset_bytes",
            "Amount of data consumed by dataset (excluding snapshots)",
            labels=self.__labelnames,
        )
        self.__mf_inodes = GaugeMetricFamily(
            "rsyncnet_account_inodes_count",
            "Number of inodes consumed by data (excluding snapshots",
            labels=self.__labelnames,
        )
        self.__mf_snap_used_free = GaugeMetricFamily(
            "rsyncnet_account_snapshot_used_free_bytes",
            "Amount of data consumed by free snapshots",
            labels=self.__labelnames,
        )
        self.__mf_snap_used_custom = GaugeMetricFamily(
            "rsyncnet_account_snapshot_used_custom_bytes",
            "Amount of data consumed by custom snapshots",
            labels=self.__labelnames,
        )
        self.__mf_idle = GaugeMetricFamily(
            "rsyncnet_account_idle_seconds",
            "Length of time that account has been idle",
            labels=self.__labelnames,
        )

    def collect(self) -> Iterator[prometheus_client.Metric]:
        resp = requests.get(self.__target, timeout=5)
        resp.raise_for_status()

        root = ET.fromstring(resp.text)
        if root.tag != "rss":
            raise Exception(f"Got XML but with unexpected root element {root.tag!r}")

        for item in root.iterfind("channel/item"):
            if not item.findtext("uid"):
                logger.debug("Skipping item %r", item.findtext("title"))
                continue

            self.collect_account(item)

        yield self.__mf_quota
        yield self.__mf_billed
        yield self.__mf_dataset
        yield self.__mf_inodes
        yield self.__mf_snap_used_free
        yield self.__mf_snap_used_custom
        yield self.__mf_idle

    def collect_account(self, item) -> Iterator[prometheus_client.Metric]:
        labelvalues = []
        for labelname in self.__labelnames:
            labelvalues.append(item.find(labelname).text or "")

        self.__mf_quota.add_metric(
            labelvalues, float(item.find("quota_gb").text) * 2**30
        )
        self.__mf_billed.add_metric(
            labelvalues, float(item.find("billed_gb").text) * 2**30
        )
        self.__mf_dataset.add_metric(
            labelvalues, float(item.find("dataset_bytes").text)
        )
        self.__mf_inodes.add_metric(labelvalues, float(item.find("inodes").text))
        self.__mf_snap_used_free.add_metric(
            labelvalues, float(item.find("snap_used_free_gb").text)
        )
        self.__mf_snap_used_custom.add_metric(
            labelvalues, float(item.find("snap_used_cust_gb").text or "0")
        )
        self.__mf_idle.add_metric(
            labelvalues, float(item.find("usage_idle_days").text) * 86400
        )
