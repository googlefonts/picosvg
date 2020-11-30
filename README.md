![CI Build Status](https://github.com/googlefonts/picosvg/workflows/Continuous%20Test%20+%20Deploy/badge.svg)
[![PyPI](https://img.shields.io/pypi/v/picosvg.svg)](https://pypi.org/project/picosvg/)
[![Dependencies](https://badgen.net/github/dependabot/googlefonts/picosvg)](https://github.com/googlefonts/picosvg/network/updates)

# picosvg

Tool to simplify SVGs. Converts an input svg into a "pico" svg:

*   Exactly 1 `<defs>` element, first child of root
*   Only gradients defined under `<defs>`
*   Only `<path>` elements without stroke or clipping after the initial `<defs>`
*   Only absolute coordinates

Clip paths and strokes are rendered into equivalent paths using [Skia](https://skia.org/) via [skia-pathops](https://github.com/fonttools/skia-pathops), `<use>` references are materialized, etc.

Some SVG features are not supported, of particular note:

*   `<filter>`
*   `<mask>`

Usage:

```shell
pip install -e .
picosvg mysvg.svg
```

## Releasing

See https://googlefonts.github.io/python#make-a-release.
