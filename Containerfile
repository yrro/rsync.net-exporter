ARG PYTHON_SUFFIX=3.11

# This is a two-stage build process. The first 'builder' container creates a
# venv into which the application's dependencies are installed. Then a wheel of
# the application is built and it too is installed into the venv.
#
FROM registry.access.redhat.com/ubi9/ubi-minimal as builder

ARG PYTHON_SUFFIX

RUN \
  microdnf -y --nodocs --setopt=install_weak_deps=0 install \
    python${PYTHON_SUFFIX} \
    python${PYTHON_SUFFIX}-pip \
  && microdnf -y clean all

# Disable ~/.cache/pip until we set up a cache volume during container image
# building.
#
ENV PIP_NO_CACHE_DIR=off PIP_ROOT_USER_ACTION=ignore

RUN python${PYTHON_SUFFIX} -m pip install build micropipenv[toml]

WORKDIR /opt/app-build

COPY pyproject.toml poetry.lock .

# Build the app's wheel.

COPY src src

RUN python${PYTHON_SUFFIX} -m build -w -v

# Create the runtime virtual environment for the app.
#
RUN \
  python${PYTHON_SUFFIX} -m venv \
    --without-pip \
    /opt/app-root/venv

# Cause subsequent pip invocations to install into the runtime virtual
# environment.
#
ENV PIP_PYTHON=/opt/app-root/venv/bin/python

# Install dependencies and the app's built wheel.

RUN \
  MICROPIPENV_PIP_BIN=pip${PYTHON_SUFFIX} \
  python${PYTHON_SUFFIX} -m micropipenv \
    install --deploy

RUN python${PYTHON_SUFFIX} -m pip install --no-deps dist/*.whl

# In the second stage, a minimal set of OS packages required to run the
# application is installed, and then the venv is copied from the 'builder'
# container.
#
FROM registry.access.redhat.com/ubi9/ubi-minimal

ARG PYTHON_SUFFIX

RUN \
  microdnf -y --nodocs --setopt=install_weak_deps=0 install \
    python${PYTHON_SUFFIX} \
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
