import contextlib
import datetime
import json
from logging import basicConfig, getLogger
from pathlib import Path
import shutil
import subprocess  # nosec
import sys
from tempfile import NamedTemporaryFile


LOGGER = getLogger(__name__)

RELEASEVER = "9"
PYTHON_SUFFIX = "3.11"


def main(argv):  # pylint: disable=unused-argument,too-many-locals

    run(
        [
            "buildah",
            "build",
            "--pull",
            "--layers",
            f"--volume={Path('~/.cache/pip').expanduser()}:/root/.cache/pip:O",
            f"--volume={Path.cwd()}:/opt/app-build:O",
            f"--build-arg=PYTHON_SUFFIX={PYTHON_SUFFIX}",
            "-t",
            "localhost/ngfw-edl-server-builder",
            "Containerfile.builder",
        ],
        check=True,
    )

    rpmmacros = Path.home() / ".rpmmacros"
    rpmmacros.touch(mode=0o644, exist_ok=True)

    with (
        buildah_from(
            ["--pull", f"registry.access.redhat.com/ubi{RELEASEVER}/ubi-micro"]
        ) as production_ctr,
        buildah_mount(production_ctr) as production_mnt,
        NamedTemporaryFile(mode="w", prefix="rpmmacros-") as temp_rpmmacros,
        mount(temp_rpmmacros.name, rpmmacros, ["bind"]),
    ):
        # There's no option for DNF to tell it to define RPM macros, so we have
        # to fall back to doing it with a config file.
        temp_rpmmacros.write("%_dbpath %{_var}/lib/rpm\n")
        temp_rpmmacros.flush()

        pbase_inspect = run(
            ["buildah", "inspect", "--type=container", production_ctr],
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        )
        base_inspect = json.loads(pbase_inspect.stdout)

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
        if prpmqa.stdout == "":
            prpmdbpath = run(
                ["rpm", "-E", "%_dbpath"], text=True, stdout=subprocess.PIPE
            )
            LOGGER.error(
                "Runtime container has no RPM packages installed. Possibly the the value of %%_dbpath within the container differs from the value defined on the host (%r).",
                prpmdbpath.stdout.strip(),
            )
            return 1

        with (
            buildah_from(["localhost/ngfw-edl-server-builder"]) as builder_ctr,
            buildah_mount(builder_ctr) as builder_mnt,
        ):
            shutil.copytree(
                builder_mnt / "opt/app-root/venv",
                production_mnt / "opt/app-root/venv",
                symlinks=True,
            )

            # We should be able to tell DNF to import the keys for repo 'foo'
            # with '--setopt=foo.gpgkey=file://...', however this fails
            # non-deterministically with the error "Parsing armored OpenPGP
            # packet(s) failed". The workaround is to manually import all the
            # keys shipped with the container image.
            for p in Path(builder_mnt / "etc/pki/rpm-gpg").iterdir():
                run(["rpm", f"--root={production_mnt}", "--import", p], check=True)

            run(
                [
                    "dnf",
                    "-y",
                    "--noplugins",
                    f"--installroot={production_mnt}",
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
                f"--installroot={production_mnt}",
                f"--releasever={RELEASEVER}",
                "clean",
                "all",
            ],
            check=True,
        )

        unwanted_pkgs = [
            f"python{PYTHON_SUFFIX}-setuptools-wheel",
            f"python{PYTHON_SUFFIX}-pip-wheel",
            "libnsl2",
            "libtirpc",
            "libtasn1",
            "keyutils-libs",
            "krb5-libs",
            "libcom_err",
            "libverto",
            "pcre",
            "gawk",
            "mpfr",
            "mpdecimal",
            "gmp",
            "grep",
            "sqlite-libs",
            "bzip2-libs",
            "xz-libs",
            "sed",
            "readline",
            "gdbm-libs",
        ]
        run(
            [
                "rpm",
                f"--root={production_mnt}",
                "--erase",
                "--allmatches",
                "--nodeps",
                *unwanted_pkgs,
            ]
        )

        prpmqa2 = run(
            ["rpm", f"--root={production_mnt}", "-qa"],
            text=True,
            stdout=subprocess.PIPE,
            check=True,
        )
        LOGGER.info("Final package list:")
        for line in sorted(prpmqa2.stdout.split("\n")):
            LOGGER.info("%s", line)

        # <https://github.com/rpm-software-management/rpm/discussions/2735>
        for p in Path(production_mnt / "usr/share/locale").iterdir():
            if p.is_dir():
                shutil.rmtree(p)

        opencontainers_image_annotations = {
            "created": datetime.datetime.now(tz=datetime.UTC).isoformat(sep=" "),
            "authors": "Sam Morris <sam@robots.org.uk>",
            "url": None,  # To be added by workflow
            "documentation": None,  # To be added by workflow
            "source": None,  # To be added by workflow
            "version": None,  # To be added by workflow
            "revision": None,  # To be added by workflow
            "vendor": "Sam Morris <sam@robots.org.uk>",
            "licenses": None,  # Lots of licenses...
            "ref.name": None,  # I have no idea what this one actually means, but I think it's not intended to be used with images anyway.
            "title": "Prometheus exporter for rsync.net",
            "description": "Prometheus exporter for rsync.net",
            "base.digest": base_inspect[
                "FromImageDigest"
            ],  # Added automatically by newer buildah versions than are available in ubuntu-latest
            "base.name": base_inspect[
                "FromImage"
            ],  # Added automatically by newer buildah versions than are available in ubuntu-latest
        }

        run(
            [
                "buildah",
                "config",
                "--env=PYTHONUNBUFFERED=1",
                "--env=PYTHONFAULTHANDLER=1",
                "--port=9770/tcp",
                "--user=1001:0",
                "--workingdir=/opt/app-root",
                "--entrypoint="
                + json.dumps(["venv/bin/python", "-I", "-m", "gunicorn"]),
                "--cmd=",
                "--stop-signal=SIGTERM",
                "--label=-",
                "--annotation=-",
                *(
                    f"--annotation=org.opencontainers.image.{k}={v}"
                    for k, v in opencontainers_image_annotations.items()
                    if v
                ),
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


@contextlib.contextmanager
def mount(device, mountpoint, options):
    run(["mount", "-o", ",".join(options), device, mountpoint], check=True)
    try:
        yield
    finally:
        run(["umount", mountpoint], check=True)


def run(args, *args_, **kwargs):
    print(f"::group::{args!r}", flush=True)
    try:
        # pylint: disable-next=subprocess-run-check
        return subprocess.run(args, *args_, **kwargs)  # nosec
    finally:
        print("::endgroup::", flush=True)


if __name__ == "__main__":
    basicConfig(level="DEBUG")
    sys.exit(main(sys.argv))


# vim: ts=8 sts=4 sw=4 et
