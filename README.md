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
$ podman run --name=rsync.net-exporter --net=host --rm --replace quay.io/yrro/rsync.net-exporter
```

You can provide any desired [Gunicorn
settings](https://docs.gunicorn.org/en/latest/settings.html), such as `--bind=`
to change the port number on which the exporter listens, as additional
arguments after the image name.

If you're not into containers, you need [Poetry](https://python-poetry.org/)
which will take care of creating a venv, installing dependencies, etc.

```
$ poetry install --only=main --extras=production

$ poetry run gunicorn
```

Once the exporter is running, use an HTTP client such as
[curl](curl) to probe for metrics:

```
$ curl localhost:9770/probe -G -d target=https://www.rsync.net:443/rss/abc123def456ghi789
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
$ curl localhost:9770/probe -G -d target=https://www.rsync.net:443/rss/abc123def456ghi789
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

The container image is built from Red Hat's [UBI
Micro](https://www.redhat.com/en/blog/introduction-ubi-micro) image. On the
host you will need [buildah](https://buildah.io/) and
[DNF](https://github.com/rpm-software-management/dnf) (which is perfectly safe
to install on non-Red Hat distros; once [this
issue](https://github.com/containers/buildah/issues/5483) is resolved, we will
be able to run `dnf` within the builder container instead, so we won't need it
installed on the host any more).

```
$ buildah unshare python3 -I build.py
```

If you don't want to install DNF, there's an unmaintained `Containerfile` that
builds a larger image:

```
$ buildah build -t rsync.net-exporter Containerfile
```

Test the container image with [podman](https://podman.io/):

```
$ poetry run pytest -m container
```
