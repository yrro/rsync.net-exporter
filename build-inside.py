"""
RUN \
  set -xeu -o pipefail; \

  setpriv -d; \

  ctr=$(buildah from --security-opt=label=disable --security-opt=seccomp=unconfined registry.access.redhat.com/ubi${RELEASEVER}/ubi-micro); \

  buildah config \
    --env=PYTHONUNBUFFERED=1 \
    --env=PYTHONFAULTHANDLER=1 \
    --port=9770/tcp \
    --user=1001:0 \
    --workingdir=/opt/app-root \
    --entrypoint='["venv/bin/python", "-m", "gunicorn"]' \
    "$ctr"; \

  mnt=$(buildah mount "$ctr"); \

  microdnf --installroot=$$mnt -y --nodocs --setopt=install_weak_deps=0 --releasever=$RELEASEVER install \
    python${PYTHON_SUFFIX}; \

  microdnf --installroot=$$mnt clean all; \

  rm -rf $${mnt}/usr/share/python${PYTHON_SUFFIX}-wheels; \

  buildah unmount "$ctr"; \

  buildah copy "$ctr" /opt/app-root/venv; \

  buildah copy gunicorn.conf.py /opt/app-root; \

  buildah commit "$ctr" rsync.net-exporter

RUN \
  podman image save -o rsync.net-exporter.img rsync.net-exporter
"""

import contextlib
import json
from logging import basicConfig, getLogger
import os
from pathlib import Path
import shutil
import subprocess
import sys


RELEASEVER = os.environ["RELEASEVER"]
PYTHON_SUFFIX = os.environ["PYTHON_SUFFIX"]

LOGGER = getLogger(__name__)


def main(argv):
    run(["setpriv", "-d"])

    with buildah_from(
        ["--pull", f"registry.access.redhat.com/ubi{RELEASEVER}/ubi-micro"]
    ) as ctr:

        run(
            [
                "buildah",
                "config",
                "--env=PYTHONUNBUFFERED=1",
                "--env=PYTHONFAULTHANDLER=1",
                "--port=9770/tcp",
                "--user=1001:0",
                "--workingdir=/opt/app-root",
                f"--entrypoint={json.dumps(['venv/bin/python', '-m', 'gunicorn'])}",
                "--cmd=",
                ctr,
            ],
            check=True,
        )

        with buildah_mount(ctr) as mnt:

            run(
                [
                    "dnf",
                    "-y",
                    "--noplugins",
                    f"--installroot={mnt}",
                    f"--releasever={RELEASEVER}",
                    "--nodocs",
                    "--setopt=install_weak_deps=0",
                    "install",
                    f"python{PYTHON_SUFFIX}",
                ],
                check=True,
            )

            run(
                [
                    "dnf",
                    "-y",
                    "--noplugins",
                    f"--installroot={mnt}",
                    f"--releasever={RELEASEVER}",
                    "clean",
                    "all",
                ],
                check=True,
            )

            shutil.rmtree(mnt / f"usr/share/python{PYTHON_SUFFIX}-wheels")

        run(["buildah", "copy", ctr, "/opt/app-root/venv"], check=True)

        run(["buildah", "commit", ctr, "rsync.net-exporter"], check=True)

        run(
            ["buildah", "save", "-o", "rsync.net-exporter.img", "rsync.net-exporter"],
            check=True,
        )

    return 0


@contextlib.contextmanager
def buildah_from(args):
    p1 = run(["buildah", "from", *args], text=True, stdout=subprocess.PIPE, check=True)
    ctr = p1.stdout.strip()
    assert ctr
    try:
        yield ctr
    finally:
        run(["buildah", "rm", ctr], check=True)


@contextlib.contextmanager
def buildah_mount(ctr):
    p2 = run(["buildah", "mount", ctr], text=True, stdout=subprocess.PIPE, check=True)
    mountpoint = p2.stdout.strip()
    assert mountpoint
    try:
        yield Path(mountpoint)
    finally:
        run(["buildah", "unmount", ctr], check=True)


def run(*args, **kwargs):
    LOGGER.debug("%r", args)
    return subprocess.run(*args, **kwargs)


if __name__ == "__main__":
    basicConfig(level="DEBUG")
    sys.exit(main(sys.argv))


# vim: ts=8 sts=4 sw=4 et
