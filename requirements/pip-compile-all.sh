#!/bin/sh
# Run pip-compile to freeze all py3*-requirements.txt files.
# You should run this every time any top-level requirements in either
# install-requirements.in or dev-requirements.in are added, removed or changed.
tox --parallel -e 'py3{6,7,8,9}-requirements'
