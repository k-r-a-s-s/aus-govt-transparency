# Design tokens for the public site (ADR-W10)

Validated 2026-10-03 with the `dataviz` skill's `scripts/validate_palette.js` (six checks:
lightness band, chroma floor, CVD separation, normal-vision floor, contrast vs surface; ordinal
ramps: monotone L, step gaps, light-end contrast, single hue). Every set below PASSES in the
mode shown. Re-run the validator before changing any of them.

## Page tokens (copied from kevinrassool.com `style.css`)

| Token | Light | Dark (`prefers-color-scheme: dark`) |
|---|---|---|
| `--paper` | `#f6f5f0` | `#191b17` |
| `--ink` | `#24251f` | `#eeeee5` |
| `--muted` | `#626458` | `#b0b3a5` |
| `--rule` | `#d2d3c8` | `#44483e` |
| `--accent` | `#176b50` | `#72c9a2` |
| `--yellow` | `#f2c42b` | `#fdd643` |

Fonts (self-hosted woff2 + OFL notices, copy from the blog's `site/fonts/`): Young Serif
(display, single weight 400), Atkinson Hyperlegible Next (body, 200-800 variable, normal +
italic), JetBrains Mono (nav, captions, eyebrows, code). `color-scheme: light dark` on `:root`.
Header: `kr.` wordmark linking to https://kevinrassool.com, nav in mono at 0.8125rem,
`aria-current="page"` underlined with `--yellow`. Body max-width 1120px, 16px gutters,
`overflow-wrap: anywhere`. Skip link, `:focus-visible` outline in `--accent`.

## Bloc colours (categorical, fixed order: Labor, Coalition, Crossbench)

| Bloc | Light (on `#f6f5f0`) | Dark (on `#191b17`) |
|---|---|---|
| Labor | `#c0392b` | `#e06355` |
| Coalition | `#2a5db0` | `#5b8ad8` |
| Crossbench | `#a0730a` | `#a8801c` |

CSS: `--bloc-labor`, `--bloc-coalition`, `--bloc-crossbench`, redefined in the dark media
query. SVG marks use `class="bloc-labor"` etc. with `fill: var(--bloc-labor)`; never a
hard-coded fill in the SVG (AC-B5). Legend always present for stacked bars; direct labels on
the three segments where space allows; 2px `--paper` gap between stacked segments.

Validator commands (run from the dataviz skill directory):
```
node scripts/validate_palette.js "#c0392b,#2a5db0,#a0730a" --mode light --surface "#f6f5f0"
node scripts/validate_palette.js "#e06355,#5b8ad8,#a8801c" --mode dark  --surface "#191b17"
```

## Sequential ramp from `--accent` (sections, entity types, single-series magnitude)

Four steps, light to dark in light mode, dark to light in dark mode (so step 4 is always the
strongest mark against the surface):

| Step | Light | Dark |
|---|---|---|
| 1 (weakest) | `#6fb997` | `#2f6b55` |
| 2 | `#3d9b75` | `#4a9a76` |
| 3 | `#176b50` | `#72c9a2` |
| 4 (strongest) | `#0b4532` | `#aee6cc` |

CSS: `--seq-1` … `--seq-4`. A single-series bar chart uses `--seq-3` (the accent) alone.

```
node scripts/validate_palette.js "#6fb997,#3d9b75,#176b50,#0b4532" --ordinal --mode light --surface "#f6f5f0"
node scripts/validate_palette.js "#2f6b55,#4a9a76,#72c9a2,#aee6cc" --ordinal --mode dark  --surface "#191b17"
```

## Chart rules carried from the dataviz skill

- One axis per chart, never dual-axis. Bars thin, 4px rounded data-ends, recessive grid.
- Text (values, axis labels, legends) in `--ink`/`--muted`, never in the series colour.
- Static SVGs: `<title>` + `<desc>`, `currentColor` for text and axes, classes for fills,
  byte-identical across builds (no random ids, no timestamps).
- Interactive (Plot) charts in the explorer: tooltip per mark, same three bloc colours via the
  CSS variables read at render time, a table view always available (the result table).
- Confidence badges are status-like but not the status palette: `medium` = `--yellow` tint
  with ink text, `low` = `--rule` outline with ink text, both with the word visible.
