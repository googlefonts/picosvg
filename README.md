[![Travis Build Status](https://travis-ci.org/rsheeter/nanosvg.svg)](https://travis-ci.org/rsheeter/nanosvg)

# nanosvg

Tool to simplify SVGs. Converts an input svg into a "nano" svg:

*   Exactly 1 `<defs>` element, first child of root
*   Only gradients defined under `<defs>`
*   Only `<path>` elements without stroke or clipping after the initial `<defs>`

Clip paths and strokes are rendered into equivalent paths, `<use>` references are materialized, etc.

Some SVG features are not supported, of particular note:

*   `<filter>`
*   `<mask>`

Usage:

```shell
pip install -e .
nanosvg mysvg.svg
```
