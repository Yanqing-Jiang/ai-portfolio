#!/bin/bash
mkdir -p /mnt/c/tmp/chrome_debug_profile
"/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe" \
  --remote-debugging-port=9222 \
  --remote-debugging-address=0.0.0.0 \
  --user-data-dir="C:\\tmp\\chrome_debug_profile" \
  --no-first-run \
  --no-default-browser-check \
  http://localhost:5173 > chrome.log 2>&1 &
echo "Chrome launched"
