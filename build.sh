#!/usr/bin/env bash

# Exit on errors
set -eux

# Install system dependencies for Chromium (Playwright)
apt-get update
apt-get install -y wget curl ca-certificates fonts-liberation libappindicator3-1 libasound2 libatk-bridge2.0-0 \
libatk1.0-0 libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 libnspr4 libnss3 libx11-xcb1 libxcomposite1 libxdamage1 \
libxrandr2 xdg-utils libu2f-udev libvulkan1 libgl1

# Install Python deps
pip install -r requirements.txt

# Install Playwright browsers
playwright install
