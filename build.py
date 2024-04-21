import contextlib
import json
from logging import basicConfig, getLogger
from pathlib import Path
import shutil
import subprocess  # nosec
import sys


LOGGER = getLogger(__name__)

RELEASEVER = "9"
PYTHON_SUFFIX = "3.11"


def main(argv):  # pylint: disable=unused-argument

    run(
        [
            "buildah",
            "build",
            "--pull",
            "--layers",
            f"--volume={Path('~/.cache/pip').expanduser()}:/root/.cache/pip:O",
            f"--build-arg=PYTHON_SUFFIX={PYTHON_SUFFIX}",
            "-t",
            "localhost/rsync.net-exporter-builder",
            "Containerfile.builder",
        ],
        check=True,
    )

    with (
        buildah_from(
            ["--pull", f"registry.access.redhat.com/ubi{RELEASEVER}/ubi-micro"]
        ) as production_ctr,
        buildah_mount(production_ctr) as production_mnt,
    ):

        (production_mnt / "opt/app-root").mkdir(parents=True)

        shutil.copy(
            "gunicorn.conf.py", production_mnt / "opt/app-root/gunicorn.conf.py"
        )

        # <https://github.com/rpm-software-management/rpm/discussions/2735>
        prpmqa = run(
            ["rpm", f"--root={production_mnt}", "-qa"],
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        )
        if len(prpmqa.stdout.split("\n")) == 1:
            prpmdbpath = run(
                ["rpm", "-E", "%_dbpath"], text=True, stdout=subprocess.PIPE
            )
            LOGGER.error(
                f"Runtime container has no RPM packages installed. Possibly the the value of %_dbpath within the container differs from the value defined on the host ({prpmdbpath.stdout.strip()!r})."
            )
            return 1

        with (
            buildah_from(["localhost/rsync.net-exporter-builder"]) as builder_ctr,
            buildah_mount(builder_ctr) as builder_mnt,
        ):
            shutil.copytree(
                builder_mnt / "opt/app-root/venv",
                production_mnt / "opt/app-root/venv",
                symlinks=True,
            )

            run(
                [
                    "dnf",
                    "-y",
                    "--noplugins",
                    f"--installroot={production_mnt}",
                    f"--releasever={RELEASEVER}",
                    "--nodocs",
                    "--setopt=install_weak_deps=0",
                    f"--setopt=ubi-9-baseos-rpms.gpgkey=file://{builder_mnt}/etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release",
                    f"--setopt=ubi-9-appstream-rpms.gpgkey=file://{builder_mnt}/etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release",
                    "install",
                    "python3.11",
                ],
                check=True,
            )

        run(
            [
                "dnf",
                "-y",
                "--noplugins",
                f"--installroot={production_mnt}",
                f"--releasever={RELEASEVER}",
                "clean",
                "all",
            ],
            check=True,
        )

        shutil.rmtree(production_mnt / f"usr/share/python{PYTHON_SUFFIX}-wheels")

        run(
            [
                "buildah",
                "config",
                "--env=PYTHONUNBUFFERED=1",
                "--env=PYTHONFAULTHANDLER=1",
                "--port=9770/tcp",
                "--user=1001:0",
                "--workingdir=/opt/app-root",
                "--entrypoint=" + json.dumps(["venv/bin/python", "-m", "gunicorn"]),
                "--cmd=",
                "--stop-signal=SIGTERM",
                production_ctr,
            ],
            check=True,
        )

        run(
            [
                "buildah",
                "commit",
                production_ctr,
                "localhost/rsync.net-exporter",
            ],
            check=True,
        )

    return 0


@contextlib.contextmanager
def buildah_from(args):
    p1 = run(["buildah", "from", *args], text=True, stdout=subprocess.PIPE, check=True)
    ctr = p1.stdout.strip()
    assert ctr  # nosec
    try:
        yield ctr
    finally:
        run(["buildah", "rm", ctr], check=True)


@contextlib.contextmanager
def buildah_mount(ctr):
    p2 = run(["buildah", "mount", ctr], text=True, stdout=subprocess.PIPE, check=True)
    mnt = p2.stdout.strip()
    assert mnt  # nosec
    try:
        yield Path(mnt)
    finally:
        run(["buildah", "unmount", ctr], check=True)


def run(args, *args_, **kwargs):
    print(f"::group::{args!r}", flush=True)
    try:
        return subprocess.run(
            args, *args_, **kwargs
        )  # nosec pylint: disable=subprocess-run-check
    finally:
        print(f"::endgroup::", flush=True)


if __name__ == "__main__":
    basicConfig(level="DEBUG")
    sys.exit(main(sys.argv))


# vim: ts=8 sts=4 sw=4 et
