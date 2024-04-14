import pytest
from unittest import mock

import prometheus_client

from rsync_net_exporter import (
    create_app,
    log_config,
    collector,
)


@pytest.fixture(scope="session")
def app():
    app = create_app(host=log_config.Host.PYTEST)
    app.config.update(
        {
            "TESTING": True,
            "RSYNC_NET_HOST": "rsync.example.net",
        }
    )
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_registry():
    return mock.create_autospec(prometheus_client.CollectorRegistry, spec_set=True)


@pytest.fixture
def mock_collector():
    return mock.create_autospec(collector.Collector, spec_set=True)


@pytest.fixture
def app_context(app):
    with app.app_context():
        yield None


@pytest.fixture(autouse=True)
def mock_app_integrations(monkeypatch, client, mock_registry, mock_collector):
    monkeypatch.setattr("prometheus_client.CollectorRegistry", mock_registry)
    monkeypatch.setattr("rsync_net_exporter.collector.Collector", mock_collector)
    return None


def test_metrics(client):
    res = client.get("/metrics")
    assert res.status.startswith("200 ")


def test_no_params(client):
    res = client.get("/probe")
    assert res.status.startswith("400 ") and "Missing" in res.text


def test_with_target_forbidden(client, app_context):
    res = client.get(
        "/probe", query_string={"target": "https://www.example.org/blah.xml"}
    )
    assert res.status.startswith("403 ") and "forbidden host" in res.text


def test_with_target_allowed(client, app_context, requests_mock):
    # given:
    target = "https://rsync.example.net/blah.xml"
    requests_mock.get(target, text="")

    # when:
    res = client.get(
        "/probe",
        query_string={"target": target},
    )

    # then:
    assert res.status.startswith("200 ")
