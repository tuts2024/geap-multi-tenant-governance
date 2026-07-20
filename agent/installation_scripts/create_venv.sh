#!/bin/bash
# Workaround: create a proper .venv for the compileall
# step (step 20/21). The base image's Dockerfile runs:
#   .venv/bin/python -m compileall \
#     "$(.venv/bin/python -c \"import site; print(site.getsitepackages()[0])\")"
# A plain symlink causes site.getsitepackages()[0] to
# return /usr/local/lib/python3.12/site-packages/ which
# is root-owned => PermissionError as appuser.
# Fix: create pyvenv.cfg so Python treats .venv/ as a
# virtualenv with writable site-packages.
set -e
PYTHON3=$(which python3)
PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
mkdir -p /code/.venv/bin
mkdir -p /code/.venv/lib/python${PY_VER}/site-packages
ln -sf "$PYTHON3" /code/.venv/bin/python
ln -sf "$PYTHON3" /code/.venv/bin/python3
cat > /code/.venv/pyvenv.cfg << PYCFG
home = $(dirname $PYTHON3)
include-system-site-packages = true
PYCFG
echo "Created .venv virtualenv (site-packages: /code/.venv/lib/python\${PY_VER}/site-packages)"
