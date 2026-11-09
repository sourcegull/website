#!/bin/sh
# Rebuilds docs/ from the Markdown in sourcegull/sourcegull, in Docker.
# Usage: tools/build-docs.sh [ref]   (default: the latest release tag)
set -eu
cd "$(dirname "$0")/.."
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD:/site" -w /site python:3.12-slim sh -c '
  pip install -q --disable-pip-version-check --target /tmp/py markdown-it-py==3.0.0 pygments==2.18.0 &&
  PYTHONPATH=/tmp/py python tools/build_docs.py "$@"' sh "$@"
