import logging
import os
import ssl
import subprocess
import time

import pytest
import requests
import trustme

from .conftest import suite


pytestmark = suite("container")

logger = logging.getLogger(__name__)


@pytest.fixture(scope="session")
def ca():
    return trustme.CA()


@pytest.fixture(scope="session")
def httpserver_ssl_context(ca):
    """
    This fixture causes pytest_httpserver to become an HTTPS server.
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_cert = ca.issue_cert("www.rsync.net")
    server_cert.configure_cert(context)
    return context


@pytest.fixture(scope="module")
def container(ca):
    with ca.cert_pem.tempfile() as ca_temp_path:
        os.chmod(ca_temp_path, 0o644)
        p = subprocess.run(
            [
                "podman",
                "run",
                "-d",
                "--rm",
                "--pull=never",
                "--network=slirp4netns:allow_host_loopback=true",
                "--publish=127.0.0.1::9770",
                "--add-host=www.rsync.net:10.0.2.2",
                f"--volume={ca_temp_path}:/tmp/ca-bundle.crt:ro,Z",
                "--env=REQUESTS_CA_BUNDLE=/tmp/ca-bundle.crt",
                "localhost/rsync.net-exporter",
                "--log-level=debug",
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        if p.returncode != 0:
            pytest.fail("Couldn't start container")

        try:
            ctr = p.stdout.rstrip()
            p2 = subprocess.run(
                ["podman", "port", ctr, "9770/tcp"],
                stdout=subprocess.PIPE,
                text=True,
                check=True,
            )
            host, sep, port_ = p2.stdout.rstrip().partition(":")
            addr = (host, int(port_))

            # XXX no better way to wait for conatiner readiness?
            time.sleep(2)

            yield addr
        finally:
            try:
                p3 = subprocess.run(
                    ["podman", "logs", ctr],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                logger.info("----- BEGIN CONTAINER LOGS ----")
                for line in p3.stdout.split("\n"):
                    if line:
                        logger.info("%s", line)
                logger.info("----- END CONTAINER LOGS ----")
            finally:
                subprocess.run(["podman", "stop", ctr], stdout=subprocess.DEVNULL, check=True)


def test_metrics(container):
    # given:
    url = f"http://{container[0]}:{container[1]}/metrics"

    # when:
    r = requests.get(url, timeout=2)

    # then:
    r.raise_for_status()


@pytest.fixture
def rsync_net_server(httpserver):
    """
    Note: to see the logs of the mock rsync.net web server, run pytest with
    --log-level=DEBUG.
    """
    httpserver.expect_request("/rss.xml", method="GET").respond_with_data(
"""\
<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0">
 <channel>
   <title>Rsync.net Usage Report RSS Feed - Sun, 14 Apr 2024 09:18:46 PT</title>
   <link>https://www.rsync.net/am/rss.xml</link>
   <lastBuildDate>Sun, 14 Apr 2024 09:18:46 PT</lastBuildDate>
   <description>This is a usage report detailing how much disk space you are using and your quota.</description>
   <language>en</language>

   <item>
     <title>Current Total Standard Usage</title>
     <link>https://www.rsync.net/am/dashboard.html</link>
     <pubDate>Sun, 14 Apr 2024 09:01:01 PT</pubDate>
     <description><![CDATA[120.15 GB]]></description>
     <guid>https://rsync.net</guid>
   </item>

   <item>
     <title>tr3289</title>
     <link>https://www.rsync.net/am/dashboard.html</link>
     <pubDate>Sun, 14 Apr 2024 09:01:01 PT</pubDate>
     <description><![CDATA["120.15 GB<br>120.00 GB Quota"]]></description>
     <guid>https://rsync.net</guid>
     <uid>tr3289</uid>
     <nickname>myspace</nickname>
     <gr></gr>
     <location>CH</location>
     <quota_gb>120</quota_gb>
     <billed_gb>120.15</billed_gb>
     <dataset_gb>120.15</dataset_gb>
     <dataset_bytes>119011805184</dataset_bytes>
     <inodes>5681</inodes>
     <free_snaps_conf>0</free_snaps_conf>
     <custom_snaps_conf></custom_snaps_conf>
     <snap_used_free_gb>12.1</snap_used_free_gb>
     <snap_used_cust_gb>14.7</snap_used_cust_gb>
     <idlewarn_days>7</idlewarn_days>
     <idlewarn_freq>24</idlewarn_freq>
     <idlewarn_min_bytes>1024</idlewarn_min_bytes>
     <usage_idle_days>2</usage_idle_days>
     <ssh_ro></ssh_ro>
     <pass_ro>1</pass_ro>
     <fs_ro></fs_ro>
   </item>

 </channel>
</rss>
""",
    )
    return httpserver


def test_probe(container, rsync_net_server):
    # given:
    url = f"http://{container[0]}:{container[1]}/probe"
    target = f"https://www.rsync.net:{rsync_net_server.port}/rss.xml"

    # when:
    r = requests.get(url, params={"target": target})

    # then:
    rsync_net_server.check()
    r.raise_for_status()
