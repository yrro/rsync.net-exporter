# This is a two-stage build process. The first 'builder' container creates a
# venv into which the application's dependencies are installed. Then a wheel of
# the application is built and it too is installed into the venv.
#
FROM registry.access.redhat.com/ubi9/ubi-minimal as builder

RUN \
  microdnf -y --nodocs --setopt=install_weak_deps=0 install \
    python3.11 \
    python3.11-pip \
  && microdnf -y clean all

# Disable ~/.cache/pip until we set up a cache volume during container image
# building.
#
ENV PIP_NO_CACHE_DIR=off PIP_ROOT_USER_ACTION=ignore

RUN python3.11 -m pip install build micropipenv[toml]

WORKDIR /opt/app-build

COPY pyproject.toml poetry.lock .

# We activate the app's venv so that micropipenv will install into it instead
# of the system Python environment.
#
# micropipenv installs all extra packages by default, so we don't need to
# specify -E production as we would with poetry.
#
RUN python3.11 -m venv /opt/app-root/venv

# pip installs into to whichever Python environment pip is itself installed
# into; micropipenv runs pip from the PATH; therefore we must put the virtual
# environment's pip command into PATH before the system-installed pip command,
# so that the virtual environment's pip command is invoked and packages are
# installed into the virtual environment.
RUN \
  PATH=/opt/app-root/venv/bin \
    /usr/bin/python3.11 -m micropipenv \
        install --deploy

# Now we build the app's wheel...

COPY src src

RUN python3.11 -m build -w

# ... and install it.

RUN /opt/app-root/venv/bin/python -m pip install --no-deps dist/*.whl

RUN /opt/app-root/venv/bin/python -m pip uninstall -y pip setuptools

# In the second stage, a minimal set of OS packages required to run the
# application is installed, and then the venv is copied from the 'builder'
# container.
#
FROM registry.access.redhat.com/ubi9/ubi-minimal

RUN \
  microdnf -y --nodocs --setopt=install_weak_deps=0 install \
    python3.11 \
    python3.11-pip \
  && microdnf -y clean all

WORKDIR /opt/app-root

COPY --from=builder /opt/app-root/venv venv

ENV \
  PYTHONUNBUFFERED=1 \
  PYTHONFAULTHANDLER=1

COPY gunicorn.conf.py .

ENTRYPOINT ["venv/bin/python", "-m", "gunicorn"]

EXPOSE 9770

LABEL \
  org.opencontainers.image.authors="Sam Morris <sam@robots.org.uk>" \
  org.opencontainers.image.description="rsync.net Prometheus exporter" \
  org.opencontainers.image.title="rsync.net exporter" \
  org.opencontainers.image.vendor="Sam Morris <sam@robots.org.uk>"

USER 1001:0

# vim: ts=8 sts=2 sw=2 et
