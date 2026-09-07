# syntax=docker/dockerfile:1
#
# Containerised build image for EditableTreeModel's PyInstaller one-file
# binary. Application source is NEVER copied into this image — it is
# bind-mounted read-only at run time (see packaging/docker/build.sh) so a
# source-only change never invalidates these layers.
#
# Build:  docker build -t editabletreemodel-build -f packaging/docker/Dockerfile packaging/docker/
# Run:    see packaging/docker/build.sh
FROM python:3.14-slim-trixie

# --- OS libraries PyInstaller's *analysis* phase needs in order to import
# PySide6 (Qt platform plugins), numpy, pandas, and gmpy2 -----------------
# binutils supplies objdump/strip, which PyInstaller shells out to when
# processing ELF binaries during collection.
# libgssapi-krb5-2 was added after a real failure: PyInstaller's
# hook-PySide6.QtNetwork.py imports PySide6.QtNetwork to probe its OpenSSL
# config, and that import chain needs libgssapi_krb5.so.2 (GSS-API/Kerberos,
# a QtNetwork runtime dependency) even though the app itself never touches
# Kerberos.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgl1 \
        libegl1 \
        libxkbcommon0 \
        libglib2.0-0 \
        libdbus-1-3 \
        libfontconfig1 \
        libgssapi-krb5-2 \
        binutils \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

# Fixed, in-image venv location (not in-project) so the venv survives even
# though /src is a read-only bind mount at run time and is not part of this
# image at all.
ENV POETRY_VIRTUALENVS_IN_PROJECT=false \
    POETRY_VIRTUALENVS_PATH=/opt/venvs \
    POETRY_NO_INTERACTION=1 \
    PIP_NO_CACHE_DIR=1

# IMPORTANT: this WORKDIR must match the `-w /src` used by build.sh at run
# time. Poetry derives its virtualenv directory name from a hash of the
# *path* to the directory containing pyproject.toml, not just its content.
# Installing here, at /src, with the exact same pyproject.toml/poetry.lock
# that will later be bind-mounted at /src, guarantees `poetry run` at run
# time resolves to the exact venv baked into this image instead of trying
# (and failing, since /src is read-only) to create a new one.
WORKDIR /src
COPY pyproject.toml poetry.lock ./
RUN poetry install --with build --no-root

# The container runs as an arbitrary uid (build.sh passes --user "$(id -u):$(id -g)").
# Nothing at run time may need to write outside /tmp and /out: HOME=/tmp
# gives poetry/pip/Qt a writable-by-anyone home (world-writable, sticky bit)
# for their caches and config.
ENV HOME=/tmp

ENTRYPOINT ["poetry", "run", "pyinstaller"]
