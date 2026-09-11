# Add support for stroke-dasharray

Add support for the SVG `stroke-dasharray` property when converting SVG strokes to paths.

The implementation should:

- Parse `stroke-dasharray` values containing comma- or space-separated numbers.
- Treat `none` as an empty dash array.
- Duplicate an odd-length dash array so that the resulting array has an even number of values.
- Support `stroke-dashoffset` when stroking paths.
- Pass the dash array and dash offset through to the path stroking implementation.
- Use a compatible version of `skia-pathops` that supports dashed strokes.
- Ensure ellipse and circle paths have a deterministic direction, starting at the 3 o'clock position and proceeding clockwise.

Add regression coverage for:
- General `stroke-dasharray` values.
- A dashed circular stroke corresponding to the BANJO U+1FA95 glyph.

The visual regression examples provided with this task are load-bearing: use them to verify that the rendered dashed stroke matches the expected result.

Do not modify unrelated behavior.
