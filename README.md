Tool to simplify SVGs. Converts an input svg into a "nano" svg:

*   Exactly 1 `<defs>` element, first child of root
*   Only gradients defined under `<defs>`
*   Only `<path>` elements without stroke or clipping after the initial `<defs>`

Clip paths and strokes are rendered into equivalent paths, `<use>` references are materialized, etc.

Some SVG features are not supported. _TODO enumerate known ones_.

Usage:

```shell
pip install -e .
nanosvg mysvg.svg
```
