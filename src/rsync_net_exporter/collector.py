from logging import getLogger
from typing import Iterator
import xml.etree.ElementTree as ET  # nosec

import prometheus_client
from prometheus_client.core import GaugeMetricFamily
import requests


logger = getLogger(__name__)


class Collector(
    prometheus_client.registry.Collector
):  # pylint: disable=too-many-instance-attributes
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

        root = ET.fromstring(resp.text)  # nosec
        if root.tag != "rss":
            raise CollectorException(
                f"Got XML but with unexpected root element {root.tag!r}"
            )

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

    def collect_account(self, item: ET.Element) -> None:
        labelvalues = []
        for labelname in self.__labelnames:
            labelvalues.append(item.findtext(labelname) or "")

        if quota_gb := item.findtext("quota_gb"):
            self.__mf_quota.add_metric(labelvalues, float(quota_gb) * 2**30)

        if billed_gb := item.findtext("billed_gb"):
            self.__mf_billed.add_metric(labelvalues, float(billed_gb) * 2**30)

        if dataset_bytes := item.findtext("dataset_bytes"):
            self.__mf_dataset.add_metric(labelvalues, float(dataset_bytes))

        if inodes := item.findtext("inodes"):
            self.__mf_inodes.add_metric(labelvalues, float(inodes))

        if snap_used_free_gb := item.findtext("snap_used_free_gb"):
            self.__mf_snap_used_free.add_metric(
                labelvalues, float(snap_used_free_gb) * 2**30
            )

        snap_used_cust_gb = item.findtext("snap_used_cust_gb") or "0"
        self.__mf_snap_used_custom.add_metric(
            labelvalues, float(snap_used_cust_gb) * 2**30
        )

        if usage_idle_days := item.findtext("usage_idle_days"):
            self.__mf_idle.add_metric(labelvalues, float(usage_idle_days) * 86400)


class CollectorException(Exception):
    pass
