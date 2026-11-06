#!/usr/bin/env bash
set -euo pipefail

RELEASE="${1:?usage: promote.sh /opt/autonomous-market-os/releases/<version>}"
APP_ROOT=/opt/autonomous-market-os
RELEASE_ROOT="$APP_ROOT/releases"
CURRENT_LINK="$APP_ROOT/current"
KNOWN_GOOD_LINK="$APP_ROOT/known-good"
BACKUP_ROOT=/var/lib/autonomous-market-os/backups
PORTFOLIO_ROOT=/var/lib/autonomous-market-os/portfolios
RECIPIENT_FILE=/etc/autonomous-market-os/backup-recipient
HEALTHCHECK=/opt/autonomous-market-os/current/deploy/u5-5/healthcheck.sh

release_real="$(realpath -e -- "$RELEASE")"
release_root_real="$(realpath -e -- "$RELEASE_ROOT")"
case "$release_real/" in
  "$release_root_real/"*) ;;
  *) echo "release is outside the release root" >&2; exit 1 ;;
esac

test -f "$release_real/apps/web/next-operator/package.json"
test -f "$release_real/apps/gateway/__main__.py"
test -d "$PORTFOLIO_ROOT"
test -f "$RECIPIENT_FILE"
command -v age >/dev/null

mkdir -p "$BACKUP_ROOT"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
tar -C "$PORTFOLIO_ROOT" -czf - paper-main \
  | age -R "$RECIPIENT_FILE" > "$BACKUP_ROOT/pre-promotion-$timestamp.tar.gz.age"
chmod 600 "$BACKUP_ROOT/pre-promotion-$timestamp.tar.gz.age"

previous=""
if test -L "$CURRENT_LINK"; then
  previous="$(readlink -e -- "$CURRENT_LINK")"
fi
if test -n "$previous"; then
  ln -sfn -- "$previous" "$KNOWN_GOOD_LINK.next"
  mv -Tf -- "$KNOWN_GOOD_LINK.next" "$KNOWN_GOOD_LINK"
elif ! test -L "$KNOWN_GOOD_LINK"; then
  echo "no known-good release slot exists" >&2
  exit 1
fi

ln -sfn -- "$release_real" "$CURRENT_LINK.next"
mv -Tf -- "$CURRENT_LINK.next" "$CURRENT_LINK"
systemctl restart market-os-python.service market-os-next.service

if ! "$HEALTHCHECK"; then
  if test -L "$KNOWN_GOOD_LINK"; then
    ln -sfn -- "$(readlink -e -- "$KNOWN_GOOD_LINK")" "$CURRENT_LINK.next"
    mv -Tf -- "$CURRENT_LINK.next" "$CURRENT_LINK"
    systemctl restart market-os-python.service market-os-next.service
    if ! "$HEALTHCHECK"; then
      echo "known-good release failed the rollback health check" >&2
      exit 1
    fi
  fi
  echo "promotion health check failed; known-good release remains active" >&2
  exit 1
fi
