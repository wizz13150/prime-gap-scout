#!/usr/bin/env bash
set -eu
cd -- "$(dirname -- "$0")"
python3 build.py --archs 86,120 --package
