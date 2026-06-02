# Changelog

## Unreleased

- Added `CHANGELOG.md` to project documentation tracking.
- Refined whole-board logic for `7mm大板` and `9mm大板`.
- Added support for `×` and three-part sizes like `7×1220×3600` and `9×1220×3040`, while ignoring the leading thickness segment in area calculations.
- Matched whole-board `(修边)` products by `商品名称 + 规格`.
- Added whole-board alias handling for `D-FW48G (修边) -> D-FW48G-04 (修边)`.
- Added fallback whole-board cost handling for `1220×3000` and `1220×3600` using `1220×2440` when no dedicated cost row exists.
- Special-cased `D-FW06G-KY-9 (不修边)` to use the higher single-square-meter cost when multiple cost rows exist.
