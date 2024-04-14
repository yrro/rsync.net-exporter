from prometheus_client.samples import Sample
import pytest

from rsync_net_exporter import collector


sample_xml = """\
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
</rss>\
"""


@pytest.mark.parametrize(
    "name,value",
    [
        ("rsyncnet_account_quota_bytes", 120.0 * 2**30),
        ("rsyncnet_account_billed_bytes", 120.15 * 2**30),
        ("rsyncnet_account_dataset_bytes", 119011805184.0),
        ("rsyncnet_account_inodes_count", 5681.0),
        ("rsyncnet_account_snapshot_used_free_bytes", 12.1 * 2**30),
        ("rsyncnet_account_snapshot_used_custom_bytes", 14.7 * 2**30),
        ("rsyncnet_account_idle_seconds", 86400.0 * 2),
    ],
)
def test_collector(requests_mock, name, value):
    # given:
    url = "https://rsync.example.net/blah.xml"
    requests_mock.get(url, text=sample_xml)
    col = collector.Collector(url)

    # when:
    metrics = {m.name: m for m in col.collect()}

    # then:
    assert (metric := metrics.get(name))
    assert metric.type == "gauge"
    assert metric.samples == [
        Sample(
            name=name,
            labels={"uid": "tr3289", "nickname": "myspace", "location": "CH"},
            value=value,
        )
    ]


sample_xml_snap_used_cust_empty = """\
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
     <snap_used_cust_gb></snap_used_cust_gb>
     <idlewarn_days>7</idlewarn_days>
     <idlewarn_freq>24</idlewarn_freq>
     <idlewarn_min_bytes>1024</idlewarn_min_bytes>
     <usage_idle_days>2</usage_idle_days>
     <ssh_ro></ssh_ro>
     <pass_ro>1</pass_ro>
     <fs_ro></fs_ro>
   </item>

 </channel>
</rss>\
"""


@pytest.mark.parametrize(
    "name,value",
    [
        ("rsyncnet_account_snapshot_used_custom_bytes", 0),
    ],
)
def test_collector_snap_custom_empty(requests_mock, name, value):
    # given:
    url = "https://rsync.example.net/blah.xml"
    requests_mock.get(url, text=sample_xml_snap_used_cust_empty)
    col = collector.Collector(url)

    # when:
    metrics = {m.name: m for m in col.collect()}

    # then:
    assert (metric := metrics.get(name))
    assert metric.type == "gauge"
    assert metric.samples == [
        Sample(
            name=name,
            labels={"uid": "tr3289", "nickname": "myspace", "location": "CH"},
            value=value,
        )
    ]
