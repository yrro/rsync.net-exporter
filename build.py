import contextlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


RELEASEVER = "9"
PYTHON_SUFFIX = "3.11"


def main(argv):
    subprocess.run(
        [
            "buildah",
            "build",
            f"--build-arg=PYTHON_SUFFIX={PYTHON_SUFFIX}",
            "-t",
            "rsync.net-exporter-builder",
            "Containerfile.builder",
        ],
        check=True,
    )

    with buildah_from(
        ["--pull", f"registry.access.redhat.com/ubi{RELEASEVER}/ubi-micro"]
    ) as (
        micro_ctr,
        micro_mountpoint,
    ):

        subprocess.run(
            [
                "dnf",
                "-y",
                "--noplugins",
                f"--installroot={micro_mountpoint}",
                f"--releasever={RELEASEVER}",
                "--nodocs",
                "--setopt=install_weak_deps=0",
                "install",
                "python3.11",
            ],
            check=True,
        )
        subprocess.run(
            [
                "dnf",
                "-y",
                "--noplugins",
                f"--installroot={micro_mountpoint}",
                f"--releasever={RELEASEVER}",
                "clean",
                "all",
            ],
            check=True,
        )

        shutil.rmtree(micro_mountpoint / f"usr/share/python{PYTHON_SUFFIX}-wheels")

        Path(micro_mountpoint / "opt/app-root").mkdir(parents=True)

        with buildah_from(["rsync.net-exporter-builder"]) as (
            builder_ctr,
            builder_mountpoint,
        ):
            shutil.copytree(
                builder_mountpoint / "opt/app-root/venv",
                micro_mountpoint / "opt/app-root/venv",
                symlinks=True,
            )

        shutil.copy(
            "gunicorn.conf.py", micro_mountpoint / "opt/app-root/gunicorn.conf.py"
        )

        subprocess.run(
            [
                "buildah",
                "config",
                "--env=PYTHONUNBUFFERED=1",
                "--env=PYTHONFAULTHANDLER=1",
                "--port=9770/tcp",
                "--user=1001:0",
                "--workingdir=/opt/app-root",
                f"--entrypoint={json.dumps(['venv/bin/python', '-m', 'gunicorn'])}",
                micro_ctr,
            ],
            check=True,
        )

        subprocess.run(
            ["buildah", "commit", micro_ctr, "rsync.net-exporter"], check=True
        )

    return 0


@contextlib.contextmanager
def buildah_from(args):
    p1 = subprocess.run(
        ["buildah", "from", *args], text=True, stdout=subprocess.PIPE, check=True
    )
    ctr = p1.stdout.strip()
    assert ctr
    try:
        p2 = subprocess.run(
            ["buildah", "mount", ctr], text=True, stdout=subprocess.PIPE, check=True
        )
        mountpoint = p2.stdout.strip()
        assert mountpoint
        try:
            yield ctr, Path(mountpoint)
        finally:
            subprocess.run(["buildah", "unmount", ctr], check=True)
    finally:
        subprocess.run(["buildah", "rm", ctr], check=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))


# vim: ts=8 sts=4 sw=4 et
