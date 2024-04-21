# rsync.net exporter

A [Prometheus](https://prometheus.io/) exporter for [rsync.net](https://rsync.net/)

Monitors storage account usage and idle times.

## Features

This exporter uses the [multi-target exporter
pattern](https://prometheus.io/docs/guides/multi-target-exporter/), where the
RSS URLs of the storage accounts to be monitored live in Prometheus' config
file.

Written in [Python](https://python.org/) (or is this an anti-feature?)

## Sample metrics

Metric definitions are not yet final!

```
# HELP rsyncnet_account_quota_bytes Account quota
# TYPE rsyncnet_account_quota_bytes gauge
rsyncnet_account_quota_bytes{location="CH",nickname="",uid="lp5570"} 1.2884901888e+011
# HELP rsyncnet_account_billed_bytes Amount of quota-consuming data (including custom snapshots)
# TYPE rsyncnet_account_billed_bytes gauge
rsyncnet_account_billed_bytes{location="CH",nickname="",uid="lp5570"} 1.290100801536e+011
# HELP rsyncnet_account_dataset_bytes Amount of data consumed by dataset (excluding snapshots)
# TYPE rsyncnet_account_dataset_bytes gauge
rsyncnet_account_dataset_bytes{location="CH",nickname="",uid="lp5570"} 1.29011805184e+011
# HELP rsyncnet_account_inodes_count Number of inodes consumed by data (excluding snapshots
# TYPE rsyncnet_account_inodes_count gauge
rsyncnet_account_inodes_count{location="CH",nickname="",uid="lp5570"} 5681.0
# HELP rsyncnet_account_snapshot_used_free_bytes Amount of data consumed by free snapshots
# TYPE rsyncnet_account_snapshot_used_free_bytes gauge
rsyncnet_account_snapshot_used_free_bytes{location="CH",nickname="",uid="lp5570"} 0.0
# HELP rsyncnet_account_snapshot_used_custom_bytes Amount of data consumed by custom snapshots
# TYPE rsyncnet_account_snapshot_used_custom_bytes gauge
rsyncnet_account_snapshot_used_custom_bytes{location="CH",nickname="",uid="lp5570"} 0.0
# HELP rsyncnet_account_idle_seconds Length of time that account has been idle
# TYPE rsyncnet_account_idle_seconds gauge
rsyncnet_account_idle_seconds{location="CH",nickname="",uid="lp5570"} 0.0
```

## How to run

If you're into containers:

```
$ podman run --name=rsync.net-exporter --net=host --rm --replace ghcr.io/yrro/rsync.net-exporter
```

If you're not into containers, you need [Poetry](https://python-poetry.org/)
which will take care of creating a venv, installing dependencies, etc.

```
$ poetry install --only=main --extras=production

$ poetry run gunicorn
```

Once the exporter is running, use an HTTP client such as
[HTTPie](https://httpie.io/) to probe for metrics:

```
$ poetry run http localhost:9770/probe target==https://www.rsync.net:443/rss/abc123def456ghi789
```

(Obtain your account's RSS URL from the storage account manager.)

## Configuring the scrape target in Prometheus

Sample `prometheus.yml` snippet:

```yaml
scrape_configs:

- job_name: rsync.net
  scrape_interval: 15s
  metrics_path: /probe
  static_configs:
  - targets: ['https://www.rsync.net:443/rss/abc123def456ghi789']
  relabel_configs:
  - source_labels: [__address__]
    target_label: __param_target
  - source_labels: [__param_target]
    target_label: instance
  - replacement: 'localhost:9770'
    target_label: __address__

- job_name: meta_rsync.net
  static_configs:
  - targets: ['localhost:9770']
```

This assumes you're running the exporter on the same machine as Prometheus. If
not, adjust the replacement string for `__address__` as appropriate.

Note: metrics about the exporter itself are exposed at `/metrics`.

## Using your own Gunicorn settings in a container

[Gunicorn settings](https://docs.gunicorn.org/en/latest/settings.html) can be
specified as command line arguments. This will override the default settings
baked in to the container image. For instance, to change the exporter's port
number:

```
$ podman run --name=rsync.net-exporter --net=host --rm --replace ghcr.io/yrro/hitron-exporter:latest --bind-address='0.0.0.0:1521'
```

## How to develop

Install development dependencies:

```
$ poetry install --with=dev
```

Run a development web server with hot code reloading:

```
$ poetry run flask run --debug
```

Probe for metrics:

```
$ poetry run http localhost:5000/probe target==https://www.rsync.net:443/rss/abc123def456ghi789
```

Run the tests:

```
$ poetry run pytest
```

... with test coverage reports:

```
$ poetry run pytest --cov --cov-report=html
```

## Before committing

Install [pre-commit](https://pre-commit.com/) and run `pre-commit install`;
this will configure your clone to run a variety of checks and you'll only be
able to commit if they pass.

If they don't work on your machine for some reason you can tell Git to let you
commit anyway with `git commit -n`.

## Building the container image

```
$ podman build -t rsync.net-exporter .
```

or

```
$ buildah build -t rsync.net-exporter --layers .
```

or

```
$ docker build -t rsync.net-exporter -f Containerfile .
```

Test the container image (with `podman`):

```
$ poetry run pytest -m container
```
