---
name: Majolica Relief Studio
colors:
  surface: '#fbf9f6'
  surface-dim: '#dbdad7'
  surface-bright: '#fbf9f6'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f5f3f0'
  surface-container: '#efeeeb'
  surface-container-high: '#eae8e5'
  surface-container-highest: '#e4e2df'
  on-surface: '#1b1c1a'
  on-surface-variant: '#4b463f'
  inverse-surface: '#30312f'
  inverse-on-surface: '#f2f0ed'
  outline: '#7c766e'
  outline-variant: '#cdc5bc'
  surface-tint: '#615e5a'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#1d1b18'
  on-primary-container: '#87837f'
  inverse-primary: '#cbc5c0'
  secondary: '#635e58'
  on-secondary: '#ffffff'
  secondary-container: '#e6ded7'
  on-secondary-container: '#67625c'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#1f1b16'
  on-tertiary-container: '#8a827c'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e7e1dc'
  primary-fixed-dim: '#cbc5c0'
  on-primary-fixed: '#1d1b18'
  on-primary-fixed-variant: '#494643'
  secondary-fixed: '#e9e1da'
  secondary-fixed-dim: '#cdc5be'
  on-secondary-fixed: '#1e1b17'
  on-secondary-fixed-variant: '#4a4641'
  tertiary-fixed: '#ebe1d9'
  tertiary-fixed-dim: '#cec5be'
  on-tertiary-fixed: '#1f1b16'
  on-tertiary-fixed-variant: '#4c4640'
  background: '#fbf9f6'
  on-background: '#1b1c1a'
  surface-variant: '#e4e2df'
typography:
  headline-lg:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Geist
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 18px
    letterSpacing: -0.005em
  body-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-md:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.03em
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 10px
    fontWeight: '400'
    lineHeight: 12px
    letterSpacing: 0.04em
  code-data:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '400'
    lineHeight: 14px
    letterSpacing: '0'
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 0.75rem
  margin: 1rem
  space-xs: 0.25rem
  space-sm: 0.375rem
  space-md: 0.5rem
  space-lg: 0.75rem
  space-xl: 1rem
---

## Brand & Style
The design system embodies the precision of a high-fidelity CAD/CAM utility balanced with the tactile heritage of Taiwanese architectural ceramic craft. Tailored for industrial designers, historical conservators, and digital fabricators converting 2D decorative tile motifs into mathematically sound 3D bas-relief models, the aesthetic merges calibrated tool ergonomics with warm museum-grade curation.

The visual style is **Warm Minimalist Precision**: an architectural drafting suite stripped of decorative excess. Hierarchy is commanded entirely through 1px hairline segmentations, hairline cross-hairs, compact density, and calibrated tonal shifts. It rejects glossy consumer tropes in favor of an exacting, workshop-bench tactile quality—purposeful, quiet, and hyper-legible.

## Colors
The palette is rooted in an unyielding warm monochrome scale derived from natural kiln clay, architectural stonework, and technical ink drafting pens.

- **Primary (`#1c1a17`)**: Near-black warm carbon. Used for dominant UI triggers, active segment states, high-priority glyphs, and primary structural typography.
- **Secondary (`#3a3631`)**: Dark warm slate. Serves secondary interactions, tool labels, parameter headers, and active indicator outlines.
- **Tertiary (`#77706a`)**: Mid warm grey. Designated for secondary dimensional units, inactive tool states, measurement ticks, and structural grid lines.
- **Neutral Canvas (`#faf8f5`)**: Clean warm off-white stone canvas. Provides an anti-glare, non-fatiguing backdrop engineered for extended spatial editing sessions.
- **Structural Accents**:
  - Border Hairline: `#e6e1da` creates rigid 1px structural partitions and workbench panel boundaries without visual noise.
  - Surface Muted / Well: `#f2efe9` defines inset control bays, slider troughs, canvas viewports, and numerical scrub fields.
  - Subtle Warm Stone: `#b8b1a8` highlights drag handles, inactive toggles, and coordinate crosshairs.

## Typography
Typography is split into two specialized functions: structural semantic framing and rigorous tabular telemetry.

- **Geist** delivers unadorned, high-clarity structural titling, section headers, and tool-group titles with tight tracking.
- **JetBrains Mono** governs all numerical data, z-depth levels, extrusion angles, displacement heights, tessellation mesh counts, coordinate axes, and micro-labels. Always enforce tabular lining figures (`font-variant-numeric: tabular-nums`) across all data displays to prevent visual jitter during real-time value scrubbing.
- All casing for technical metadata, axis tags (X, Y, Z), and tool indicators must be rendered in uppercase with positive letter spacing (`0.03em` to `0.04em`).

## Layout & Spacing
The layout employs an ultra-dense, fixed-rail CAD tool paradigm. The viewport centers a fixed aspect-ratio 3D rendering canvas, flanked by dockable, persistent utility inspectors on the left and right.

- **Desktop (>= 1280px)**: 3-column studio layout. Left rail (280px fixed) for vector layer extraction, tile symmetry detection, and relief profiles. Center region (fluid flex) for the WebGL/Three.js elevation viewport and orthographic guides. Right rail (320px fixed) for volumetric displacement parameters, toolpath slicing, and mesh decimation controls.
- **Tablet (768px - 1279px)**: 2-column layout. The left inspector collapses into an iconified docking toolbar; the right parameter inspector converts to an overlay drawer.
- **Mobile (< 768px)**: Single viewport stack. Center canvas takes 60vh; parameter rails become bottom sheets with a horizontal tool ribbon.
- **Rhythm**: Grounded in a strict 4px sub-grid with baseline component spacing tokens (`space-xs` = 4px, `space-sm` = 6px, `space-md` = 8px, `space-lg` = 12px, `space-xl` = 16px). Margins between nested inspection fields never exceed 8px to maintain information density.

## Elevation & Depth
The system is built upon **Structural Hairline Division and Inset Wells**, avoiding conventional blurred drop shadows to retain blueprint clarity.

- **Surfaces**: Depth is established via surface nesting rather than elevation off the canvas.
  - Level 0 (Base Canvas): `#faf8f5`
  - Level 1 (Tool Shelves & Inspectors): `#ffffff` with a continuous `1px solid #e6e1da` perimeter.
  - Level 2 (Recessed Scrub Inputs & Troughs): `#f2efe9` with an inner 1px hairline stroke (`#e6e1da`).
- **Shadows**: Omit ambient drop shadows across toolbars, buttons, and inspectors. Use only a single micro-shadow on active floating context menus or flyout tooltips: `0 1px 3px rgba(28, 26, 23, 0.08)`.
- **Viewport Canvas**: The central relief view is defined by a 1px border (`#e6e1da`) with a subtle 0.5px inner raster grid representing 10mm ceramic tile unit intervals.

## Shapes
Geometry is disciplined, utilitarian, and ergonomic. 

- Standard component corner radius is fixed at `6px` (`roundedness: 1`), providing an exact balance between modern industrial precision and tactile accessibility.
- Recessed numeric inputs, segment buttons, and tool chips all share this exact `6px` radius to create uniform rows of interactive cells.
- Internal status tags, coordinate badges, and slider thumbs use a tighter `3px` corner radius.
- No fully pill-shaped or circular buttons are permitted in the utility suite; circular geometry is strictly reserved for directional compass indicators, arc angle scrubbers, and rotational 3D gizmos.

## Components

### Buttons & Interactive Triggers
- **Dimensions**: Strictly 32px height across standard controls (`space-sm` top/bottom padding, 10px horizontal padding). Compact density is non-negotiable.
- **Primary Action (Generate Mesh, Export STL/OBJ)**: Solid `#1c1a17` background, `#faf8f5` text, 6px border radius, no border. Hover shifts to `#3a3631`. Active state scales subtly down (`scale(0.98)`).
- **Secondary Tool Button**: Solid `#ffffff` background, `1px solid #e6e1da`, `#1c1a17` text. Hover shifts background to `#f2efe9` and border to `#b8b1a8`.
- **Ghost / Tool Ribbon Button**: Transparent background, 32x32px square. Renders vector icons in `#77706a`. Hover: `#ffffff` background with `#e6e1da` border; icon becomes `#1c1a17`.

### Numeric Scrub Fields & Coordinate Inputs
- **Structure**: 32px height, 6px radius, set on an inset `#f2efe9` background with a `1px solid #e6e1da` outline.
- **Typography**: `JetBrains Mono` 11px (`label-md`). Axis label (X, Y, Z, or mm) locked to the left in `#77706a`. Numerical value right-aligned in `#1c1a17`.
- **Interaction**: Click and drag horizontally to scrub values; single-click selects all text for direct manual entry. Focus triggers an absolute 1px border highlight of `#1c1a17`.

### Sliders (Displacement, Draft Angle, Bevel)
- **Track**: 4px height, `#e6e1da` background with a filled active segment in `#1c1a17`.
- **Thumb**: 12px × 12px square with a 3px radius, `#ffffff` surface, bounded by a 1.5px solid `#1c1a17` rim. Zero shadow; tactile drag feel.

### Segmented Controls & Tool Selectors
- **Container**: Enclosed 32px height container in `#f2efe9` with a 1px border `#e6e1da` and 2px internal padding.
- **Segments**: Equal-width tab segments. Active segment features a `#ffffff` background, 4px border radius, 1px border `#e6e1da`, and bold `#1c1a17` text. Inactive segments have no background, with text in `#77706a`.

### Cards & Inspector Groups
- **Structure**: Enclosed in `#ffffff` panels with `1px solid #e6e1da` borders and 6px corner radii.
- **Header**: Compact 28px header section, separated from the content body by a 1px horizontal `#e6e1da` rule. Text styled in Geist 11px uppercase (`label-md`), tracking `0.04em`, colored `#77706a`.

### Status Indicators & Badges
- **Format**: Pill-shaped or 3px rounded rectangular chips (18px total height), featuring `JetBrains Mono` 10px text.
- **Colors**: Mesh polygon count, GPU render time, and manifold water-tight validation tags use `#f2efe9` backgrounds, `#77706a` borders, and `#3a3631` text.

### Layer & Vector Extraction Lists
- **Rows**: Flat, dense 28px height rows with horizontal borders (`1px solid #f2efe9`).
- **States**: Hover reveals `#f2efe9` tint. Selected layer renders a 2px vertical `#1c1a17` bar on the left edge with a `#f7f5f0` surface fill.