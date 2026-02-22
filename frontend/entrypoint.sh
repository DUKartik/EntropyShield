#!/bin/sh
set -e

if [ -z "$BACKEND_URL" ]; then
  echo "Error: BACKEND_URL environment variable is not set."
  exit 1
fi

echo "Substituting BACKEND_URL ($BACKEND_URL) into nginx configuration..."
sed "s|\\\${BACKEND_URL}|${BACKEND_URL}|g" /etc/nginx/nginx.conf.tmp > /etc/nginx/conf.d/default.conf

echo "Starting Nginx..."
exec nginx -g "daemon off;"
