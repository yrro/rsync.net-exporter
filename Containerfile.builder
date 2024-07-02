FROM registry.access.redhat.com/ubi9/ubi-minimal as builder

ARG PYTHON_SUFFIX

RUN \
  microdnf -y --nodocs --setopt=install_weak_deps=0 install \
    python${PYTHON_SUFFIX} \
    python${PYTHON_SUFFIX}-pip \
  && microdnf -y clean all

ENV PYTHONSAFEPATH=1

ENV \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  PIP_ROOT_USER_ACTION=ignore

RUN python${PYTHON_SUFFIX} -m pip install build micropipenv[toml]

WORKDIR /opt/app-build

# Build the app's wheel.

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

# vim: ts=8 sts=2 sw=2 et
