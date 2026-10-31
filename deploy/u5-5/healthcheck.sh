#!/usr/bin/env bash
set -euo pipefail

curl --fail --silent --show-error --max-time 5 \
  -H 'Host: 127.0.0.1' \
  http://127.0.0.1:8787/readyz >/dev/null

curl --fail --silent --show-error --max-time 5 \
  -H 'Host: 127.0.0.1' \
  http://127.0.0.1:3000/healthz >/dev/null
