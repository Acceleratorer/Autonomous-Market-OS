#!/usr/bin/env bash
set -euo pipefail

# Tailscale Serve is the only browser ingress. Both application services stay
# bound to loopback; this command does not publish Python directly.
tailscale serve reset
tailscale serve --https=443 http://127.0.0.1:3000
