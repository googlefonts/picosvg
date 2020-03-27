#!/usr/bin/env bash
#
# Things that should be run (and pass) before submitting code.
#

# everything should succeed
set -e

black src tests
pytest
pytype

echo "Seems OK :)"