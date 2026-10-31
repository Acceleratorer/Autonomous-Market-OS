#!/usr/bin/env bash
set -euo pipefail

APP_ROOT=/opt/autonomous-market-os
CURRENT_LINK="$APP_ROOT/current"
KNOWN_GOOD_LINK="$APP_ROOT/known-good"
HEALTHCHECK="$APP_ROOT/current/deploy/u5-5/healthcheck.sh"

target="$(readlink -e -- "$KNOWN_GOOD_LINK")"
test -d "$target"
ln -sfn -- "$target" "$CURRENT_LINK.next"
mv -Tf -- "$CURRENT_LINK.next" "$CURRENT_LINK"
systemctl restart market-os-python.service market-os-next.service
"$HEALTHCHECK"
