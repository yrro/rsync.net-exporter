from unittest.mock import Mock

from prometheus_client.samples import Sample
import pytest

from rsync_net_exporter.collector import Collector


@pytest.fixture
def client():
    client = Mock(spec_set=Client)

    def get_data(dataset):
        if dataset == client.Dataset.SYSTEM_MODEL:
            return {"modelName": "CGNV4-FX4", "skipWizard": "1"}
        elif dataset == client.Dataset.SYSINFO:
            return [
                {
                    "LRecPkt": "12.12M Bytes",
                    "LSendPkt": "40.14M Bytes",
                    "WRecPkt": "40.25M Bytes",
                    "WSendPkt": "11.77M Bytes",
                    "aftrAddr": "",
                    "aftrName": "",
                    "delegatedPrefix": "",
                    "hwVersion": "2D",
                    "lanIPv6Addr": "",
                    "lanIp": "192.0.2.0/24",
                    "rfMac": "84:0B:7C:01:02:03",
                    "serialNumber": "ABC123",
                    "swVersion": "4.5.10.201-CD-UPC",
                    "systemTime": "Fri Jun 17, 2022, 17:09:10",
                    "systemUptime": "10 Days,17 Hours,33 Minutes,47 Seconds",
                    "timezone": "1",
                    "wanIp": "203.0.113.1/24",
                }
            ]
        elif dataset == client.Dataset.CMINIT:
            return [
                {
                    "bpiStatus": "AUTH:authorized, TEK:operational",
                    "dhcp": "Success",
                    "downloadCfg": "Success",
                    "eaeStatus": "Secret",
                    "findDownstream": "Success",
                    "hwInit": "Success",
                    "networkAccess": "Permitted",
                    "ranging": "Success",
                    "registration": "Success",
                    "timeOfday": "Secret",
                    "trafficStatus": "Enable",
                }
            ]

        elif dataset == client.Dataset.DSINFO:
            return [
                {
                    "channelId": "9",
                    "frequency": "426250000",
                    "modulation": "2",
                    "portId": "1",
                    "signalStrength": "17.400",
                    "snr": "40.946",
                },
                {
                    "channelId": "14",
                    "frequency": "5030",
                    "modulation": "9",
                    "portId": "2",
                    "signalStrength": "11.030",
                    "snr": "13.243",
                },
            ]
        elif dataset == client.Dataset.USINFO:
            return [
                {
                    "bandwidth": "6400000",
                    "channelId": "2",
                    "frequency": "39400000",
                    "portId": "1",
                    "scdmaMode": "ATDMA",
                    "signalStrength": "36.000",
                },
                {
                    "bandwidth": "18",
                    "channelId": "13",
                    "frequency": "250",
                    "portId": "2",
                    "scdmaMode": "QFSP28",
                    "signalStrength": "40.030",
                },
            ]
        else:
            pytest.fail(f"Unknown dataset {dataset!r}")

    client.get_data.side_effect = get_data
    return client


@pytest.fixture
def metrics(client):
    # given:
    collector = Collector(client)

    # when:
    return {m.name: m for m in collector.collect()}


def test_metrics_upstream_signal_strength(metrics):
    # then:
    assert (m := metrics.get("hitron_channel_upstream_signal_strength_dbmv"))
    assert m.type == "gauge"
    assert m.samples == [
        Sample(
            name=m.name,
            labels={"port": "1", "channel": "2", "frequency": "39400000"},
            value=36.0,
        ),
        Sample(
            name=m.name,
            labels={"port": "2", "channel": "13", "frequency": "250"},
            value=40.03,
        ),
    ]


def test_metrics_upstream_bandwidth(metrics):
    # then:
    assert (m := metrics.get("hitron_channel_upstream_bandwidth"))
    assert m.type == "gauge"
    assert m.samples == [
        Sample(
            name=m.name,
            labels={"port": "1", "channel": "2", "frequency": "39400000"},
            value=6400000.0,
        ),
        Sample(
            name=m.name,
            labels={"port": "2", "channel": "13", "frequency": "250"},
            value=18.0,
        ),
    ]


def test_metrics_downstream_signal_strength(metrics):
    # then:
    assert (m := metrics.get("hitron_channel_downstream_signal_strength_dbmv"))
    assert m.type == "gauge"
    assert m.samples == [
        Sample(
            name=m.name,
            labels={"port": "1", "channel": "9", "frequency": "426250000"},
            value=17.4,
        ),
        Sample(
            name=m.name,
            labels={"port": "2", "channel": "14", "frequency": "5030"},
            value=11.03,
        ),
    ]


def test_metrics_downstream_signal_snr(metrics):
    # then:
    assert (m := metrics.get("hitron_channel_downstream_snr"))
    assert m.type == "gauge"
    assert m.samples == [
        Sample(
            name=m.name,
            labels={"port": "1", "channel": "9", "frequency": "426250000"},
            value=40.946,
        ),
        Sample(
            name=m.name,
            labels={"port": "2", "channel": "14", "frequency": "5030"},
            value=13.243,
        ),
    ]


def test_metrics_system_uptime(metrics):
    # then:
    assert (m := metrics.get("hitron_system_uptime_seconds"))
    assert m.type == "counter"
    assert m.samples == [
        Sample(name=m.name + "_total", labels={}, value=927227.0),
    ]


def test_metrics_system_clock(metrics):
    # then:
    assert (m := metrics.get("hitron_system_clock_timestamp_seconds"))
    assert m.type == "gauge"
    assert m.samples == [Sample(m.name, labels={}, value=1655485750.0)]


@pytest.mark.parametrize(
    "input_,expected",
    [
        ("Fri Jun 17, 2022, 17:09:10", 1655485750.0),
        ("Tue Feb 01, 2011, 16:12:05", 1296576725.0),
        ("Not a date", None),
    ],
)
def test_parse_clock(input_, expected):
    assert Collector.parse_clock(input_) == expected


@pytest.mark.parametrize(
    "input_,expected",
    [
        ("17 Days,13 Hours,11 Minutes,7 Seconds", 1516267.0),
        ("Unparsable string", None),
    ],
)
def test_parse_uptime(input_, expected):
    assert Collector.parse_uptime(input_) == expected


def test_metrics_network_transmit(metrics):
    # then:
    assert (m := metrics.get("hitron_network_transmit_bytes"))
    assert m.type == "counter"
    assert m.samples == [
        Sample(m.name + "_total", labels={"device": "lan"}, value=40140000.0),
        Sample(m.name + "_total", labels={"device": "wan"}, value=11770000.0),
    ]


def test_metrics_network_recieve(metrics):
    # then:
    assert (m := metrics.get("hitron_network_receive_bytes"))
    assert m.type == "counter"
    assert m.samples == [
        Sample(m.name + "_total", labels={"device": "lan"}, value=12120000.0),
        Sample(m.name + "_total", labels={"device": "wan"}, value=40250000.0),
    ]


@pytest.mark.parametrize(
    "input_,expected",
    [
        ("123 Bytes", 123),
        ("234K Bytes", 234000),
        ("345M Bytes", 345000000),
        ("456G Bytes", 456000000000),
        ("567T Bytes", None),  # unknown pkt factor
        ("13 not matching string", None),
    ],
)
def test_parse_pkt(input_, expected):
    assert Collector.parse_pkt(input_) == expected


def test_metrics_system(metrics):
    # then:
    assert (m := metrics.get("hitron_system"))
    assert m.type == "info"
    assert m.samples[0].labels == {
        "model_name": "CGNV4-FX4",
        "serial_number": "ABC123",
        "software_version": "4.5.10.201-CD-UPC",
        "hardware_version": "2D",
    }


def test_metrics_cm_bpi(metrics):
    # then:
    assert (m := metrics.get("hitron_cm_bpi"))
    assert m.type == "info"
    assert m.samples[0].labels == {"auth": "authorized", "tek": "operational"}
