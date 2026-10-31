# BlockTrace — Stitch UI Generation Prompt

Copy everything below the line into Stitch. Generate all 5 screens together so navigation
and the design system stay consistent across them. Request React + Tailwind export.

---

Design a 5-screen web product called **BlockTrace** — "Explainable blockchain crime
investigation." It's a professional forensics/security tool, not a consumer app — think
a security-alert dashboard crossed with a modern SaaS product. Bold, confident, high
contrast. No playful illustrations, no rounded cartoon icons.

## Design System

**Colors:**
- Background: #FAF3E1 (warm cream)
- Surface / card background: #F5E7C6 (deeper cream)
- Primary text / dark elements: #222222 (near-black)
- Primary accent (brand + Medium-risk badges): #FF6D1F (bold orange)
- Text muted/secondary: #6B6255
- Border/divider: #E0D3B0
- High-risk / sanctioned / danger: #D62839 (deep red — distinct from the brand orange so
  "High risk" never gets confused with a normal button or the Medium tier)
- Low-risk / success: #4C8C4A (muted green)
- Peel-chain accent: #2E6F95 (muted blue)
- Circular-flow accent: #6B4E8E (muted violet)

Use black (#222222) as the dominant UI color for headers, nav, and primary buttons —
treat cream as the canvas, not the foreground. Orange is an accent for CTAs and Medium-risk
badges, not a background wash.

**Typography:**
- Headings: Space Grotesk, bold, slightly tight letter-spacing
- Body text: Inter
- Wallet addresses / hashes / code: JetBrains Mono (monospace) — always render blockchain
  addresses in this font, never in the body font

**Components style:**
- Cards: deeper-cream background (#F5E7C6), 1px border (#E0D3B0), rounded corners
  (10-12px), no heavy shadows
- A "risk badge" component: small pill-shaped badge, color-coded (green=Low, orange=Medium,
  deep red=High/Critical), used throughout
- Buttons: solid black (#222222) or solid orange (#FF6D1F) for primary actions, outlined
  style for secondary actions
- Use a left-border accent stripe (3px, colored) on list-item cards to indicate category/severity

**Overall tone:** light mode, bold and high-contrast, dense but organized, data-forward,
trustworthy, zero marketing fluff on the app screens (only the homepage should have
marketing tone).

---

## Screen 1: Homepage (marketing/landing page)

**Nav bar:** logo mark + "BlockTrace" wordmark on the left. Center/right: "Product",
"How it Works", "Verified Cases" links, and a solid orange "Launch App" button.

**Hero section:** Large headline: "Trace crypto crime. Verify every finding." Subheadline:
"BlockTrace investigates cryptocurrency wallets, flags suspicious patterns with full
transparency, and issues cryptographic proof that its findings can't be silently altered."
Two buttons: "Launch App" (solid orange) and "See a Real Case" (outlined). Background: a
subtle, abstract dark network-graph illustration (dots and connecting lines, orange glow),
very faint, sitting behind the hero text.

**Problem section:** Headline "Public data isn't the same as understandable data."
Two-column layout: left side shows a wall of raw unreadable transaction hashes/hex fading
out; right side shows the same data as a clean labeled graph. Short paragraph explaining
that investigators currently trace stolen funds manually, wallet by wallet.

**How It Works section:** 4 numbered steps in a horizontal row (stack on mobile), each
with a small icon, title, and one sentence:
1. "Pick a wallet" — Load a verified real case, or investigate any address
2. "We trace the network" — Follows the money automatically, hop by hop
3. "Patterns get flagged" — Five independent, explainable detection techniques
4. "Get proof" — Export a cryptographically verifiable investigation certificate

**Features grid:** 3x3 (or 4x2) grid of feature cards, each with an icon, title, one-line
description. Features: Hub Activity Detection, Fund-Splitting Detection, Peel Chain
Detection, Round-Number Detection, Circular Flow Detection, Honest Confidence Scoring,
Sanctions Screening, Multi-Chain Support, Verifiable Certificates.

**Differentiation section:** Headline "Transparent by design." Short comparison-style
layout — two columns, "Closed Platforms" vs "BlockTrace" — closed platforms: "Proprietary
black-box scoring", "No independent verification", "Enterprise-only pricing"; BlockTrace:
"Every flag shows its exact reasoning", "Cryptographically verifiable findings", "Open and
accessible". Keep this factual and calm, not aggressively salesy.

**Verified Cases showcase:** Section headline "Tested against real, documented incidents."
3 cards in a row, each representing a real hack: "Ronin Bridge Hack — $600M, 2022",
"Poly Network Hack — $611M, 2021", "Wormhole Bridge Hack — $321M, 2022" — each card has
the case name, dollar amount, year, and a "View Investigation" link.

**Final CTA band:** Full-width orange-tinted section, headline "Start an investigation in
seconds," "Launch App" button.

**Footer:** BlockTrace logo, short tagline, links (Product, Cases, Docs), and a small
disclaimer line: "Detection results are heuristic indicators, not proof of wrongdoing."

---

## Screen 2: Investigate (main app screen)

Layout: a left sidebar (fixed, ~300px) + large main content area. This is the working
tool, not marketing — dense and functional.

**Sidebar sections (stacked vertically, each in its own card):**
1. "Example Investigations" — 3 buttons, one per verified case (Ronin Bridge, Poly
   Network, Wormhole), each showing the case name and dollar amount
2. "Investigate a Wallet" — chain selector dropdown (Ethereum / BNB Smart Chain /
   Polygon), a monospace text input for wallet address, a "Hops deep" slider (1-3), a
   "Transactions per wallet" slider (5-30), and a solid orange "Expand Graph" button
3. "Trace a Specific Path" — two monospace inputs (From wallet / To wallet), a max-hops
   slider (1-6), and a "Find Path" button — framed as "show only the route between two
   wallets"

**Main content area:** a large dark canvas showing an interactive node-graph
visualization (dots = wallets in black, connecting lines = transactions, deep-red dots for
sanctioned wallets, a small star icon for labeled/known entities). Above the graph, a
thin toolbar with a text filter input ("Filter by address") and a small info banner area
(for messages like "Showing path from X to Y — 2 paths found").

---

## Screen 3: Findings

**Top section — "What This Trail Shows":** a highlighted card with a colored left
border (orange), containing 3-5 short paragraphs of plain-English narrative text, ending in
a smaller italic disclaimer line about heuristic indicators not being proof.

**Sanctions Screening section:** full-width, list of cards — each showing a wallet
address (monospace), the sanctioned entity name, issuing authority, and a red "SANCTIONED"
badge on the right.

**Wallet Risk Overview section:** full-width, list of cards, each showing: wallet address
(monospace) on top, a smaller muted line below listing which specific techniques flagged
it (e.g. "Hub Activity · Fan-Out · Peel Chain"), and a right-aligned tier badge
("High · 3 signals" in deep red, "Medium · 2 signals" in orange, "Low · 1 signal" in green).
Show 5 by default with a "Show all N flagged wallets" expandable link/button below.

**Detection technique grid:** below the risk overview, a 3-column row followed by a
2-column row of panel cards:
- Row 1: "Hub Wallets" (black left-border), "High Fan-Out" (deep-red left-border), "Peel
  Chains" (muted-blue left-border)
- Row 2: "Round-Number Transactions" (orange left-border), "Circular Flows" (muted-violet
  left-border)

Each panel has a title with icon, a one-line plain-English description of what the
technique detects, then a list of result rows (wallet address + a metric badge specific
to that technique), capped at 5 visible with a "Show all N matches" expandable link.

---

## Screen 4: Certificates

Two-column layout.

**Left column — "Issue a New Certificate":** short explanatory text: "Generates a
cryptographic hash of this investigation's current findings, chained to the previous
certificate. Anyone holding the certificate file can later re-verify it — without trusting
this server." A solid orange button "Generate Certificate for Current Findings." Below it, a
result state showing the issued hash (truncated, monospace, in a highlighted box) and a
"Download Certificate" button.

**Right column — "Verify an Existing Certificate":** a file upload dropzone ("Upload a
certificate JSON file"), and below it a result state showing either a green success card
("✅ Certificate is intact") or a red error card ("❌ Certificate does not match — findings
may have been altered").

---

## Screen 5: Cases & Reports

**Top section — "Investigation Report":** a card explaining PDF export, with a solid
orange "Generate PDF Report" button and, after generation, a "Download Report" button.

**Bottom section — "Saved Investigation Cases":** a table/list layout — each row shows:
case name, saved date, edge/transaction count, and two right-aligned actions: "Load" (orange-outlined
outlined button) and a small trash/delete icon button. Above the list, a text input +
"Save Current Case" button to save the currently loaded investigation under a new name.

---

Connect all 5 screens with a consistent left sidebar navigation on the 4 app screens
(Investigate, Findings, Certificates, Cases & Reports) — sidebar nav items: a BlockTrace
logo at top, then "Investigate", "Findings", "Certificates", "Cases & Reports", with the
current screen highlighted in orange. The Homepage does not use this sidebar — it uses the
top nav bar described above instead.
