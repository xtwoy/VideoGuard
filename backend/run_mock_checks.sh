#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
VG_PYTHON=python3
if [ -x .venv/bin/python ]; then VG_PYTHON=.venv/bin/python; fi
"$VG_PYTHON" -m unittest discover -s tests -v
"$VG_PYTHON" -m fixtures.validate
"$VG_PYTHON" -m fixtures.generate --check
"$VG_PYTHON" -m fixtures.truth_table
"$VG_PYTHON" -m fixtures.compare_pead --check
echo 'Mock validation passed. Reports are in backend/reports.'
