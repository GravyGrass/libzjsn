#!/bin/bash

set -e
set -u

cd "$(dirname "$0")"
exec python3 -u adv-fetcher.py Boat Boat.sqlite3 >> adv-fetcher."$(date +%Y%m%d-%H%M%S)".log 2>&1
