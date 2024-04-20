import contextlib
import json
from logging import basicConfig, getLogger
import os
from pathlib import Path
import shutil
import subprocess  # nosec
import sys


LOGGER = getLogger(__name__)

RELEASEVER = "9"
PYTHON_SUFFIX = "3.11"


def main(argv):  # pylint: disable=unused-argument
    with group("Create builder container"):
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

            # Prevent runner environment from affecting how DNF works (e.g.,
            # updating ~runner/.rpmdb instead of /var/lib/rpmdb)
            environ = {
                # "HOME": "/root",
                # "SHELL": "/bin/bash",
                # "PATH": "/root/.local/bin:/root/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin",
            }

            run(["rpm", f"--root={production_mnt}", "-qa"], env=environ, check=False)

            run(["setpriv", "-d"])
            run(["printenv"])

            with group("Import RPM PGP keys"):
                # According to
                # <https://bugzilla.redhat.com/show_bug.cgi?id=2039261#c1> the
                # --setopt= options to dnf should take care of this, but I can't
                # figure out the right option names for the UBI repos. In the mean
                # time we can import the keys into the production container's RPM
                # database before running DNF.
                #
                run(
                    [
                        "strace",
                        "-e",
                        "%file",
                        "rpm",
                        f"--root={production_mnt}",
                        # f"--dbpath={production_mnt}/var/lib/rpm",
                        "-vv",
                        "--import",
                        production_mnt / "etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release",
                    ],
                    env=environ,
                    check=True,
                )

            run(["rpm", f"--root={production_mnt}", "-qa"], check=False)

            with group("Install packages"):
                run(
                    [
                        "strace",
                        "-e",
                        "%file",
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
                    env=environ,
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
                    env=environ,
                    check=True,
                )

            run(["rpm", f"--root={production_mnt}", "-qa"], check=False)

            shutil.rmtree(production_mnt / f"usr/share/python{PYTHON_SUFFIX}-wheels")

            # ~runner/.rpmdb created by the rpm --import command; let's not
            # remove it because we should probably figure out _why_
            # /var/lib/rpmdb was not used...
            # shutil.rmtree(production_mnt / "home/runner")

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
            ["buildah", "commit", production_ctr, "localhost/rsync.net-exporter"],
            check=True,
        )

    return 0


@contextlib.contextmanager
def group(title):
    print(f"::group::{title}")
    try:
        yield
    finally:
        print("::endgroup")


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


def run(*args, **kwargs):
    LOGGER.debug("%r", args)
    p = subprocess.run(*args, **kwargs)  # nosec pylint: disable=subprocess-run-check
    LOGGER.debug("%r", p)
    return p


if __name__ == "__main__":
    basicConfig(level="DEBUG")
    sys.exit(main(sys.argv))


# vim: ts=8 sts=4 sw=4 et
