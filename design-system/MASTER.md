# R/LAB Research Assistant

## Direction

- Product: local, desktop scientific research operations workspace.
- Style: Data-Dense Swiss, based on a strict grid, typography-first hierarchy and objective information display.
- Palette: black, white and neutral gray with signal red `#d71920`; semantic green, yellow and danger red are reserved for real states.
- Typography: Inter / Microsoft YaHei UI for interface copy; JetBrains Mono for identifiers, dates, hashes and parameters.
- Effects: precise 1px separators, fixed 2px panel/control corners, no persistent panel shadows, no hover movement.

## Layout

- Keep the 248px desktop sidebar light and visually continuous with the workspace.
- Use full-width metric bands and dense tables for comparison instead of decorative card grids.
- Keep primary content at least twice as wide as navigation, filters or supporting panels.
- Long collections require search/filter, page-size controls, pagination and bulk actions.
- Dashboard activity uses a 1:2 split: experiment-plan index on the left, recent records on the right.

## Components

- Signal red is for branding, primary commands, active indicators and links.
- Status badges always include text and use semantic tokens; never communicate state by color alone.
- Buttons and icon controls retain a 44px effective hit area and visible theme-aware focus rings.
- Panels are unshadowed; dialogs and floating tools may use elevation.
- The interface has one fixed light Swiss palette. Theme variants, dark mode and custom backgrounds are retired.

## Avoid

- Blue or fluorescent-green accents in the interface.
- Rounded decorative cards, nested cards, hover scaling and oversized empty states.
- Unbounded lists, hidden bulk actions, hard-coded component colors or mobile-only composition.
