[![CI Build Status](https://github.com/googlefonts/picosvg/workflows/Continuous%20Test%20+%20Deploy/badge.svg)](https://github.com/googlefonts/picosvg/actions/workflows/ci.yml?query=workflow%3ATest)
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

## Test

Install the dev dependencies specified in [`extras_require`](https://github.com/googlefonts/picosvg/blob/main/setup.py#L36-L40).

```shell
pip install -e .[dev]
pytest
```

If you use zsh, it will prompt an error(`zsh: no matches found: .[dev]`). Please use the following command:

```shell
pip install -e '.[dev]'
```

You can also use [pytest](https://docs.pytest.org/) to test the specified files individually.

```shell
pytest tests/svg_test.py
```

If you need to test a certain function (for example: test_topicosvg), please execute:

```shell
pytest tests/svg_test.py::test_topicosvg
```

If you need to display detailed diff information, please execute:
```shell
pytest tests/svg_test.py::test_topicosvg --vv
```
## Releasing

See https://googlefonts.github.io/python#make-a-release.
