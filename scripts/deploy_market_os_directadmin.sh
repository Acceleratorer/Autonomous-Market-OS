#!/usr/bin/env bash

set -Eeuo pipefail

: "${DIRECTADMIN_HOST:?DIRECTADMIN_HOST is required}"
: "${DIRECTADMIN_USER:?DIRECTADMIN_USER is required}"
: "${DIRECTADMIN_PASSWORD:?DIRECTADMIN_PASSWORD is required}"
: "${DIRECTADMIN_CA_BUNDLE:?DIRECTADMIN_CA_BUNDLE is required}"
: "${REMOTE_DIR:?REMOTE_DIR is required}"
: "${GITHUB_SHA:?GITHUB_SHA is required}"
: "${GITHUB_RUN_ATTEMPT:?GITHUB_RUN_ATTEMPT is required}"
: "${RUNNER_TEMP:?RUNNER_TEMP is required}"

readonly EXPECTED_REMOTE_DIR="/domains/accel.io.vn/public_html/market-os"
readonly REMOTE_PARENT="/domains/accel.io.vn"
readonly RUN_SUFFIX="${GITHUB_SHA}-${GITHUB_RUN_ATTEMPT}"
readonly STAGING_DIR="${REMOTE_PARENT}/.market-os-release-${RUN_SUFFIX}"
readonly ROLLBACK_DIR="${REMOTE_PARENT}/.market-os-rollback"
readonly PRESERVED_ROLLBACK_DIR="${REMOTE_PARENT}/.market-os-rollback-preserved-${RUN_SUFFIX}"
readonly FAILED_DIR="${REMOTE_PARENT}/.market-os-failed-${RUN_SUFFIX}"
readonly ARCHIVE_NAME=".market-os-${RUN_SUFFIX}.zip"
readonly ARCHIVE_PATH="${REMOTE_PARENT}/${ARCHIVE_NAME}"
readonly LOCAL_ARCHIVE="market-os-${GITHUB_SHA}.zip"
readonly CA_FILE="${RUNNER_TEMP}/directadmin-ca-bundle.pem"
readonly API_BASE="https://${DIRECTADMIN_HOST}:2222/api"
readonly PUBLIC_URL="https://accel.io.vn/market-os/"
readonly PREVIOUS_HTML="${RUNNER_TEMP}/market-os-before.html"
readonly CHECK_HTML="${RUNNER_TEMP}/market-os-check.html"

if [[ "${REMOTE_DIR}" != "${EXPECTED_REMOTE_DIR}" ]]; then
  echo "Refusing unexpected deployment path: ${REMOTE_DIR}" >&2
  exit 1
fi
if [[ ! "${DIRECTADMIN_HOST}" =~ ^[A-Za-z0-9.-]+$ ]]; then
  echo "DIRECTADMIN_HOST must be a hostname without scheme or port." >&2
  exit 1
fi
if [[ ! "${GITHUB_SHA}" =~ ^[0-9a-f]{40,64}$ || ! "${GITHUB_RUN_ATTEMPT}" =~ ^[1-9][0-9]*$ ]]; then
  echo "Invalid release identity." >&2
  exit 1
fi
if [[ ! -s "${CA_FILE}" || ! -f "${LOCAL_ARCHIVE}" ]]; then
  echo "The verified CA bundle or SHA-named release archive is missing." >&2
  exit 1
fi

readonly DA_CURL=(
  curl --silent --show-error --cacert "${CA_FILE}"
  --user "${DIRECTADMIN_USER}:${DIRECTADMIN_PASSWORD}"
  --connect-timeout 20 --max-time 180
)

fail() {
  echo "$1" >&2
  return 1
}

urlencode() {
  python3 - "$1" <<'PY'
import sys
import urllib.parse

print(urllib.parse.quote(sys.argv[1], safe=""))
PY
}

da_request() {
  "${DA_CURL[@]}" --fail-with-body "$@"
}

da_stat_status() {
  local path="$1"
  local query
  query="$(urlencode "${path}")"
  local status
  status="$("${DA_CURL[@]}" \
    --request GET \
    --output /dev/null \
    --write-out '%{http_code}' \
    "${API_BASE}/filemanager/stat?path=${query}")"

  # The same DirectAdmin host's Wuwa Map flow uses 409 from this stat endpoint
  # for a missing file-manager path. Other errors are never treated as absent.
  if [[ "${status}" == 409 ]]; then
    printf '404\n'
  else
    printf '%s\n' "${status}"
  fi
}

da_remove() {
  local path="$1"
  local payload
  payload="$(python3 - "${path}" <<'PY'
import json
import sys

print(json.dumps({"paths": [sys.argv[1]], "trash": False}))
PY
)"
  da_request \
    --request POST \
    --header 'Content-Type: application/json' \
    --data "${payload}" \
    "${API_BASE}/filemanager-actions/remove"
}

da_move() {
  local source="$1"
  local destination="$2"
  local payload
  payload="$(python3 - "${source}" "${destination}" <<'PY'
import json
import sys

print(json.dumps({"source": sys.argv[1], "destination": sys.argv[2], "overwrite": False}))
PY
)"
  da_request \
    --request POST \
    --header 'Content-Type: application/json' \
    --data "${payload}" \
    "${API_BASE}/filemanager-actions/move"
}

da_mkdir() {
  local path="$1"
  local payload
  payload="$(python3 - "${path}" <<'PY'
import json
import sys

print(json.dumps({"path": sys.argv[1]}))
PY
)"
  da_request \
    --request POST \
    --header 'Content-Type: application/json' \
    --data "${payload}" \
    "${API_BASE}/filemanager-actions/mkdir"
}

da_extract() {
  local source="$1"
  local destination="$2"
  local payload
  payload="$(python3 - "${source}" "${destination}" <<'PY'
import json
import sys

print(json.dumps({
    "source": sys.argv[1],
    "destinationDir": sys.argv[2],
    "members": [],
    "mergeAndOverwrite": False,
}))
PY
)"
  da_request \
    --request POST \
    --header 'Content-Type: application/json' \
    --data "${payload}" \
    "${API_BASE}/filemanager-actions/extract-archive"
}

da_upload_archive() {
  local directory_query
  local name_query
  directory_query="$(urlencode "${REMOTE_PARENT}")"
  name_query="$(urlencode "${ARCHIVE_NAME}")"
  da_request \
    --request POST \
    --form "file=@${LOCAL_ARCHIVE};type=application/zip" \
    "${API_BASE}/filemanager-actions/upload?dir=${directory_query}&name=${name_query}&perm=420&overwrite=false"
}

da_chmod_staging() {
  local payload
  payload="$(python3 - "${STAGING_DIR}" <<'PY'
import json
import sys

print(json.dumps({"paths": [sys.argv[1]], "perm": 493}))
PY
)"
  da_request \
    --request POST \
    --header 'Content-Type: application/json' \
    --data "${payload}" \
    "${API_BASE}/filemanager-actions/chmod"
}

public_status() {
  local url="$1"
  curl --silent --show-error --location --connect-timeout 20 --max-time 60 \
    --output "${CHECK_HTML}" --write-out '%{http_code}' "${url}"
}

check_preserved_routes() {
  local path
  local status
  for path in / /waifu /waifu/ /wuwa-map /wuwa-map/; do
    status="$(public_status "https://accel.io.vn${path}?market-os-release=${GITHUB_SHA}")"
    if [[ "${status}" != 200 ]]; then
      fail "Preserved route ${path} returned HTTP ${status}."
    fi
  done
}

read_live_index_status() {
  local query="$1"
  curl --silent --show-error --location --connect-timeout 20 --max-time 60 \
    --output "${PREVIOUS_HTML}" --write-out '%{http_code}' "${PUBLIC_URL}?${query}"
}

assert_live_release() {
  local status
  local actual_hash
  status="$(read_live_index_status "v=${RUN_SUFFIX}")"
  if [[ "${status}" != 200 ]]; then
    fail "Production preview returned HTTP ${status}."
  fi
  actual_hash="$(sha256sum "${PREVIOUS_HTML}" | cut -d' ' -f1)"
  if [[ "${actual_hash}" != "${RELEASE_INDEX_SHA256}" ]]; then
    fail "Production index does not match the ${GITHUB_SHA} artifact."
  fi

  status="$(public_status "https://accel.io.vn/market-os/DEPLOYMENT.txt?v=${RUN_SUFFIX}")"
  if [[ "${status}" != 403 && "${status}" != 404 ]]; then
    fail "Deployment metadata should be denied, got HTTP ${status}."
  fi
  check_preserved_routes
}

assert_previous_live_state() {
  local status
  status="$(read_live_index_status "rollback-check=${RUN_SUFFIX}")"
  if [[ "${status}" != "${PREVIOUS_HTTP_STATUS}" ]]; then
    fail "Rollback route returned HTTP ${status}; expected ${PREVIOUS_HTTP_STATUS}."
  fi
  if [[ -n "${PREVIOUS_INDEX_SHA256}" ]]; then
    local actual_hash
    actual_hash="$(sha256sum "${PREVIOUS_HTML}" | cut -d' ' -f1)"
    if [[ "${actual_hash}" != "${PREVIOUS_INDEX_SHA256}" ]]; then
      fail "Rollback index does not match the pre-deploy production page."
    fi
  fi
  check_preserved_routes
}

release_index_sha256() {
  sha256sum site/market-os/index.html | cut -d' ' -f1
}

readonly RELEASE_INDEX_SHA256="$(release_index_sha256)"

previous_release_present=0
current_move_started=0
staging_move_started=0
previous_http_status=""
previous_index_sha256=""
promotion_started=0

rollback_on_error() {
  local original_status="$?"
  trap - ERR
  set +e

  echo "Deployment failed; reconciling DirectAdmin state and restoring the pre-deploy site when possible."
  if [[ "${promotion_started}" == 1 ]]; then
    local production_status
    local rollback_status
    local preserved_status
    production_status="$(da_stat_status "${REMOTE_DIR}")" || production_status=000
    rollback_status="$(da_stat_status "${ROLLBACK_DIR}")" || rollback_status=000
    preserved_status="$(da_stat_status "${PRESERVED_ROLLBACK_DIR}")" || preserved_status=000

    if [[ "${staging_move_started}" == 1 && "${production_status}" == 200 ]]; then
      local staging_status
      staging_status="$(da_stat_status "${STAGING_DIR}")" || staging_status=000
      if [[ "${staging_status}" == 404 ]]; then
        da_move "${REMOTE_DIR}" "${FAILED_DIR}" || echo "Could not retain the failed release at ${FAILED_DIR}." >&2
        production_status="$(da_stat_status "${REMOTE_DIR}")" || production_status=000
        rollback_status="$(da_stat_status "${ROLLBACK_DIR}")" || rollback_status=000
      else
        echo "Production state is ambiguous; staging still reports HTTP ${staging_status}, so it was left untouched." >&2
      fi
    fi

    if [[ "${current_move_started}" == 1 && "${previous_release_present}" == 1 && "${production_status}" == 404 && "${rollback_status}" == 200 ]]; then
      da_move "${ROLLBACK_DIR}" "${REMOTE_DIR}" || echo "Could not restore the rollback directory." >&2
      production_status="$(da_stat_status "${REMOTE_DIR}")" || production_status=000
      rollback_status="$(da_stat_status "${ROLLBACK_DIR}")" || rollback_status=000
    fi

    if [[ "${preserved_status}" == 200 && "${rollback_status}" == 404 ]]; then
      da_move "${PRESERVED_ROLLBACK_DIR}" "${ROLLBACK_DIR}" || echo "Could not restore the earlier rollback slot." >&2
    fi

    if ! assert_previous_live_state; then
      echo "Automatic rollback verification failed; inspect DirectAdmin paths under ${REMOTE_PARENT}." >&2
    fi
  fi
  exit "${original_status}"
}

trap rollback_on_error ERR

for path in "${STAGING_DIR}" "${PRESERVED_ROLLBACK_DIR}" "${FAILED_DIR}" "${ARCHIVE_PATH}"; do
  status="$(da_stat_status "${path}")"
  if [[ "${status}" != 404 ]]; then
    fail "Release path ${path} already exists or returned unexpected HTTP ${status}."
  fi
done

check_preserved_routes

current_status="$(da_stat_status "${REMOTE_DIR}")"
rollback_status="$(da_stat_status "${ROLLBACK_DIR}")"
if [[ "${current_status}" == 404 && "${rollback_status}" == 200 ]]; then
  echo "Recovering the previous production directory before starting this release."
  da_move "${ROLLBACK_DIR}" "${REMOTE_DIR}"
  current_status=200
  rollback_status=404
fi
if [[ "${current_status}" != 200 && "${current_status}" != 404 ]]; then
  fail "Unexpected DirectAdmin status ${current_status} for ${REMOTE_DIR}."
fi
if [[ "${rollback_status}" != 200 && "${rollback_status}" != 404 ]]; then
  fail "Unexpected DirectAdmin status ${rollback_status} for ${ROLLBACK_DIR}."
fi

previous_http_status="$(read_live_index_status "pre-deploy=${RUN_SUFFIX}")"
if [[ "${previous_http_status}" != 200 && "${previous_http_status}" != 404 ]]; then
  fail "Pre-deploy preview returned unexpected HTTP ${previous_http_status}."
fi
if [[ "${previous_http_status}" == 200 ]]; then
  previous_index_sha256="$(sha256sum "${PREVIOUS_HTML}" | cut -d' ' -f1)"
fi
if [[ "${current_status}" == 200 ]]; then
  previous_release_present=1
fi

da_mkdir "${STAGING_DIR}"
da_upload_archive
da_extract "${ARCHIVE_PATH}" "${STAGING_DIR}"
da_chmod_staging
for name in index.html .htaccess DEPLOYMENT.txt; do
  status="$(da_stat_status "${STAGING_DIR}/${name}")"
  if [[ "${status}" != 200 ]]; then
    fail "Staging is missing ${name} (DirectAdmin HTTP ${status})."
  fi
done

if [[ "${current_status}" == 200 ]]; then
  if [[ "${rollback_status}" == 200 ]]; then
    promotion_started=1
    da_move "${ROLLBACK_DIR}" "${PRESERVED_ROLLBACK_DIR}"
  fi
  promotion_started=1
  current_move_started=1
  da_move "${REMOTE_DIR}" "${ROLLBACK_DIR}"
else
  promotion_started=1
fi

staging_move_started=1
da_move "${STAGING_DIR}" "${REMOTE_DIR}"
assert_live_release

if [[ "$(da_stat_status "${PRESERVED_ROLLBACK_DIR}")" == 200 ]]; then
  da_remove "${PRESERVED_ROLLBACK_DIR}" || echo "Warning: older rollback cleanup failed." >&2
fi
da_remove "${ARCHIVE_PATH}" || echo "Warning: release archive cleanup failed; leaving ${ARCHIVE_PATH}." >&2
trap - ERR

if [[ "${previous_release_present}" == 1 ]]; then
  echo "Deployment verified. Previous production is retained at ${ROLLBACK_DIR}."
else
  echo "First deployment verified. There was no previous Market OS release to retain."
fi
