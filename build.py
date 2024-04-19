import contextlib
import json
from logging import basicConfig, getLogger
from pathlib import Path
import shutil
import subprocess
import sys


LOGGER = getLogger(__name__)

RELEASEVER = "9"
PYTHON_SUFFIX = "3.11"


def main(argv):
    run(
        [
            "buildah",
            "build",
            f"--build-arg=PYTHON_SUFFIX={PYTHON_SUFFIX}",
            "-t",
            "localhost/rsync.net-exporter-builder",
            "Containerfile.builder",
        ],
        check=True,
    )

    with buildah_from(
        ["--pull", f"registry.access.redhat.com/ubi{RELEASEVER}/ubi-micro"]
    ) as production_ctr:

        with buildah_mount(production_ctr) as production_mnt:

            (production_mnt / "opt/app-root").mkdir(parents=True)

            with buildah_from(["localhost/rsync.net-exporter-builder"]) as builder_ctr:
                with buildah_mount(builder_ctr) as builder_mnt:
                    shutil.copytree(
                        builder_mnt / "opt/app-root/venv",
                        production_mnt / "opt/app-root/venv",
                        symlinks=True,
                    )

            shutil.copy(
                "gunicorn.conf.py", production_mnt / "opt/app-root/gunicorn.conf.py"
            )

            # According to
            # <https://bugzilla.redhat.com/show_bug.cgi?id=2039261#c1> the
            # --setopt= options to dnf should take care of this, but I can't
            # figure out the right option names for the UBI repos. In the mean
            # time we can import the keys into the production container's RPM
            # database before running DNF.
            #
            run(
                [
                    "rpm",
                    f"--root={production_mnt}",
                    "--import",
                    production_mnt / "etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release",
                ],
                check=True,
            )

            run(
                [
                    "dnf",
                    "-y",
                    "--noplugins",
                    f"--installroot={production_mnt}",
                    f"--setopt=ubi-9-appstream-rpms.gpgkey={production_mnt}/etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release",
                    f"--setopt=ubi-9-baseos-rpms.gpgkey={production_mnt}/etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release",
                    f"--releasever={RELEASEVER}",
                    "--nodocs",
                    "--setopt=install_weak_deps=0",
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
                production_ctr,
            ],
            check=True,
        )

        run(
            ["buildah", "commit", production_ctr, "localhost/rsync.net-exporter"],
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
    mnt = p2.stdout.strip()
    assert mnt
    try:
        yield Path(mnt)
    finally:
        run(["buildah", "unmount", ctr], check=True)


def run(*args, **kwargs):
    LOGGER.debug("%r", args)
    return subprocess.run(*args, **kwargs)


if __name__ == "__main__":
    basicConfig(level="DEBUG")
    sys.exit(main(sys.argv))


# vim: ts=8 sts=4 sw=4 et
