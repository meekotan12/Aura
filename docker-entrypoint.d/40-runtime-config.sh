#!/bin/sh
set -eu

: "${PORT:=80}"
: "${AURA_API_BASE_URL:=/__backend__}"
: "${AURA_API_TIMEOUT_MS:=15000}"

envsubst '${AURA_API_BASE_URL} ${AURA_API_TIMEOUT_MS}' \
  < /opt/aura/runtime-config.js.template \
  > /usr/share/nginx/html/runtime-config.js

envsubst '${PORT} ${BACKEND_ORIGIN}' \
  < /opt/aura/nginx.conf.template \
  > /etc/nginx/conf.d/default.conf
