---
name: BlockTrace Forensic System
colors:
  surface: '#fff8f6'
  surface-dim: '#eed5cb'
  surface-bright: '#fff8f6'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#fff1ec'
  surface-container: '#ffe9e2'
  surface-container-high: '#fde3d9'
  surface-container-highest: '#f7ddd3'
  on-surface: '#261813'
  on-surface-variant: '#594137'
  inverse-surface: '#3c2d27'
  inverse-on-surface: '#ffede7'
  outline: '#8d7165'
  outline-variant: '#e1bfb2'
  surface-tint: '#a43e00'
  primary: '#a43e00'
  on-primary: '#ffffff'
  primary-container: '#ff6d1f'
  on-primary-container: '#5b1f00'
  inverse-primary: '#ffb596'
  secondary: '#5f5e5e'
  on-secondary: '#ffffff'
  secondary-container: '#e2dfde'
  on-secondary-container: '#636262'
  tertiary: '#006591'
  on-tertiary: '#ffffff'
  tertiary-container: '#00a4e9'
  on-tertiary-container: '#003650'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdbcd'
  primary-fixed-dim: '#ffb596'
  on-primary-fixed: '#360f00'
  on-primary-fixed-variant: '#7d2d00'
  secondary-fixed: '#e5e2e1'
  secondary-fixed-dim: '#c8c6c5'
  on-secondary-fixed: '#1b1c1c'
  on-secondary-fixed-variant: '#474746'
  tertiary-fixed: '#c9e6ff'
  tertiary-fixed-dim: '#89ceff'
  on-tertiary-fixed: '#001e2f'
  on-tertiary-fixed-variant: '#004c6e'
  background: '#fff8f6'
  on-background: '#261813'
  surface-variant: '#f7ddd3'
typography:
  display-lg:
    fontFamily: Space Grotesk
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.4'
  address-md:
    fontFamily: JetBrains Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: '1.2'
    letterSpacing: -0.01em
  label-caps:
    fontFamily: Space Grotesk
    fontSize: 12px
    fontWeight: '700'
    lineHeight: '1'
    letterSpacing: 0.05em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
  gutter: 24px
  margin: 32px
---

## Brand & Style

The design system is engineered for **Explainable Blockchain Forensics**. It balances the clinical precision of a security tool with a bold, confident aesthetic that asserts authority in high-stakes investigations.

The visual style is **Corporate Modern with a Tactical Edge**. It utilizes high-contrast interfaces and a warm, archival background palette to reduce eye strain during long investigation sessions. The aesthetic avoids the "dark mode hacker" cliché in favor of a sophisticated, document-centric approach that feels like a modern intelligence dossier. Every element is designed to make complex transaction flows and criminal patterns immediately legible and legally defensible.

## Colors

The palette is anchored by a warm, paper-like foundation to provide a "forensic report" feel. 

- **Primary Accent:** `#FF6D1F` (Bold Orange) is used exclusively for interactive actions and critical path highlights.
- **Core Neutrals:** The background (`#FAF3E1`) and surface (`#F5E7C6`) create a subtle layered effect without relying on harsh shadows. Primary text is set in `#222222` for maximum readability.
- **Functional Semantics:** 
    - **High-Risk:** Deep Red (`#D62839`) for illicit entities.
    - **Low-Risk:** Muted Green (`#4C8C4A`) for verified exchanges or clean wallets.
    - **Pattern Recognition:** Blue (`#2E6F95`) and Violet (`#6B4E8E`) are used to categorize specific laundering techniques like peel chains and circular flows within graph visualizations.

## Typography

This design system employs a tri-font strategy to separate intent:

1.  **Space Grotesk (Headlines):** Used for structural markers and page titles. Its technical, geometric character reinforces the "cutting-edge science" aspect of the tool.
2.  **Inter (Body):** The workhorse for all descriptions, tooltips, and explanatory text. It provides a neutral, highly legible canvas for complex data.
3.  **JetBrains Mono (Data):** Specifically reserved for blockchain hashes, wallet addresses, and code snippets. The monospaced nature ensures that character-level differences in addresses are easily detectable by the human eye.

## Layout & Spacing

The layout utilizes a **12-column fixed grid** for dashboard views, ensuring that analytical widgets maintain consistent proportions. 

- **The Investigation Sidebar:** A fixed 280px left-hand navigation allows for quick switching between "Graph View," "Transaction Logs," and "Entity Intelligence."
- **Spacing Rhythm:** An 8px base unit (4px for tight data density) drives the layout. 
- **Data Density:** In forensic views, margins are tightened to 16px to maximize the amount of visible data on screen, while editorial or report-generation views increase margins to 40px+ to aid focus.

## Elevation & Depth

Depth is communicated through **Tonal Layering and Sharp Outlines** rather than soft shadows. This maintains the "professional tool" aesthetic.

- **Level 0 (Base):** `#FAF3E1` (Background).
- **Level 1 (Cards/Widgets):** `#F5E7C6` (Surface) with a 1px solid border of `#E0D3B0`.
- **Level 2 (Popovers/Modals):** Same as Level 1 but with a sharp, 4px offset "hard shadow" in a 10% opacity version of the primary text color, creating a physical "stacked paper" effect.
- **Interactions:** Hovering over a card or list item shifts the border color from `#E0D3B0` to the primary orange (`#FF6D1F`) or a darker grey, providing immediate tactile feedback without changing the layout.

## Shapes

The shape language is controlled and geometric.

- **Containers:** Main UI cards and content surfaces use a `10px` to `12px` corner radius. This softens the high-contrast professional look just enough to feel modern.
- **Form Inputs:** Utilize a `4px` radius for a more rigid, "input-ready" feel.
- **Badges/Chips:** All risk indicators and tags use a **Pill-shaped** radius. This distinction ensures that status indicators are never confused with clickable buttons or layout containers.

## Components

### Buttons
- **Primary:** Solid `#FF6D1F` with white or `#222222` text. Bold, sans-serif caps.
- **Secondary:** Transparent background with a 2px `#222222` border.
- **Ghost:** No border, text-only using the Primary Accent color for actions like "View More."

### Badges (Risk Indicators)
- Small, pill-shaped elements. They must include an icon (e.g., a shield or warning triangle) alongside the text label to ensure accessibility for colorblind users. Backgrounds use a 15% opacity of the functional color (Red/Green/Blue) with a 100% opacity text color.

### Forensic Cards
- Cards contain a "Header" section with the `label-caps` typography and a "Body" section. They are always bordered (`1px #E0D3B0`).

### Address Fields
- Wallet addresses are displayed in `address-md` (JetBrains Mono). They should feature a "Click to Copy" action that appears on hover and a "short-hand" middle-truncation (e.g., 0x123...abc).

### Input Fields
- Background matches the surface color (`#F5E7C6`) but darkens by 5% on focus. The border shifts to the primary orange accent when active.

### Data Tables
- Clean, no vertical lines. Horizontal dividers use a 1px `#E0D3B0` line. Header rows use `label-caps` with a slightly darker background tint.