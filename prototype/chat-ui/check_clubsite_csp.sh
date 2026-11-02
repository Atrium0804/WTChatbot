#!/usr/bin/env bash
# PROTOTYPE (issue #14) — empirische check: stuurt de clubsite (AllUnited,
# wtcwoerden.nl) CSP- of X-Frame-Options-headers die een iframe vanaf onze
# origin zouden blokkeren? Draai: bash check_clubsite_csp.sh
set -u
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
URLS=(
  "https://www.wtcwoerden.nl/"
  "https://www.wtcwoerden.nl/index.php?page=Agenda&sid=1"
  "https://www.wtcwoerden.nl/index.php?page=674&sid=1"
)
for url in "${URLS[@]}"; do
  echo "== $url =="
  curl -sI -A "$UA" --max-time 20 "$url" | grep -iE "^(HTTP/|content-security-policy|x-frame-options)" \
    || echo "  (geen CSP / X-Frame-Options header)"
  echo "  CSP-termen in HTML-body:"
  curl -s -A "$UA" --max-time 20 "$url" \
    | grep -ioE "content-security-policy|frame-ancestors|frame-src" | sort -u \
    || echo "  (geen CSP-meta in body)"
done
