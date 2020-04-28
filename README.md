[![Travis Build Status](https://travis-ci.org/googlefonts/picosvg.svg?branch=master)](https://travis-ci.org/googlefonts/picosvg)
[![PyPI](https://img.shields.io/pypi/v/picosvg.svg)](https://pypi.org/project/picosvg/)
[![pyup](https://pyup.io/repos/github/googlefonts/picosvg/shield.svg)](https://pyup.io/repos/github/googlefonts/picosvg)

# picosvg

Tool to simplify SVGs. Converts an input svg into a "pico" svg:

*   Exactly 1 `<defs>` element, first child of root
*   Only gradients defined under `<defs>`
*   Only `<path>` elements without stroke or clipping after the initial `<defs>`

Clip paths and strokes are rendered into equivalent paths using [Skia](https://skia.org/) via [skia-pathops](https://github.com/fonttools/skia-pathops), `<use>` references are materialized, etc.

Some SVG features are not supported, of particular note:

*   `<filter>`
*   `<mask>`

Usage:

```shell
pip install -e .
picosvg mysvg.svg
```

## How to cut a new release

Use `git tag -a` to make a new annotated tag, or `git tag -s` for a GPG-signed annotated tag,
if you prefer.

Name the new tag with with a leading 'v' followed by three MAJOR.MINOR.PATCH digits, like in
[semantic versioning](https://semver.org/). Look at the existing tags for examples.

In the tag message write some short release notes describing the changes since the previous
tag.

Finally, push the tag to the remote repository (e.g. assuming upstream is called `origin`):

```
$ git push origin v0.4.3
```

This will trigger the CI to build the distribution packages and upload them to the
[Python Package Index](https://pypi.org/project/picosvg/) automatically, if all the tests
pass successfully.
