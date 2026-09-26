# YSH Internal Apps Design System

Design system for YSH Property's internal business web applications. It takes the working visual language of **Groundwork** (YSH's knowledge-gathering portal) as the product foundation and ties it to the public brand at [ysh.com.au](https://ysh.com.au/) through the logo, the navy and gold brand pair, and the tone of the site.

## Company and product context

**YSH Property** (YSH Property Group, trading historically as Your Style Homes) is a Brisbane property company with three arms: property development, property investment education and property management. It works across Queensland and Victoria, including purpose-built rooming houses. Corporate office: Building B, Level 1, 172 Evans Road, Salisbury QLD 4107.

Internal products this system serves:

1. **Groundwork**: staff sign in with an emailed link, share the files they work from (including unofficial spreadsheets and workarounds), and map how their work flows on a BPMN canvas. Mapping sessions can be recorded and transcribed. Live mapping runs on the Jev decision model (TypeSafe Jev via OpenRouter's System One API), and drafting and review run on a reasoning model (gtp-6-luna in this system's examples). AI output is always a draft a person keeps or drops. Modelling follows Real-Life BPMN: an overview pass (standard path only, everything else to a parking lot), then a detail pass per person, then combine views.
2. **Internal business app starter**: a business-agnostic modular-monolith foundation (access, audit ledger, work runtime, operations, content, guarded AI gateway) with a responsive shell and no business screens. This system re-skins that shell so every new app looks like Groundwork.
3. **Excel to web app**: a utility, integrated with Groundwork, that turns a shared workbook into a governed web app. The repository was empty at build time, so its UI kit is a **proposed** flow built only from existing parts.

## Sources

- Codebase `groundwork/` (local mount). Key files: `frontend/src/styles.css` (all tokens and component styling), `frontend/src/pages/*.tsx`, `frontend/src/canvas/nodes.tsx`, `palette.ts`, `LivePanel.tsx`, `frontend/index.html` (font), `CLAUDE.md` (writing rules), `backend/app/processing/xlsx_profile.py`.
- Codebase `internal-business-app-starter/` (local mount). Key files: `apps/web/index.html`, `apps/web/src/styles.css`, `docs/BASE-SPECIFICATION.md`, `docs/spreadsheet-webapp.md`.
- GitHub [https://github.com/rdb420/groundwork](https://github.com/rdb420/groundwork) (same code as the local mount; see `github.md`).
- GitHub [https://github.com/rdb420/excel-to-webapp](https://github.com/rdb420/excel-to-webapp): empty repository at build time.
- Website [https://ysh.com.au/](https://ysh.com.au/) and `uploads/ysh-website-scrape.md` (page text; logos and imagery fetched from the site). The PDF scrape named in the brief was not in the project.

Explore those repositories to go deeper than this summary when designing new screens; the code is the source of truth.

## Index

- `styles.css`: entry point, `@import`s only.
- `tokens/`: `fonts.css`, `colors.css`, `typography.css`, `spacing.css`, `base.css` (element defaults), `components.css` and `canvas.css` (gw- classes the components use), `shell.css` (ibs- starter shell).
- `fonts/`: Atkinson Hyperlegible 400/700 + italics, Montserrat (latin woff2).
- `assets/logo/`: YSH logo files from ysh.com.au, Groundwork mark. `assets/icons/`: BPMN task markers. `assets/imagery/`: one website photo.
- `guidelines/`: foundation specimen cards (Colors, Type, Spacing, Brand).
- `components/`: React primitives, one folder per concern, each with `.jsx`, `.d.ts`, `.prompt.md` and a card.
- `ui_kits/groundwork/`, `ui_kits/internal-app-starter/`, `ui_kits/excel-to-webapp/`: click-through screens.
- `SKILL.md`, `github.md`, `thumbnail.html`.

## Components

Namespace in cards and kits: `window.YSHInternalAppsDesignSystem_a013d5`.

- **core**: Button, SegToggle, Status, Tag, Chip
- **forms**: Field, Check, Segmented, OptionGroup, DropZone
- **data**: Card, Door, Doors, FileCard, Tiles, Rows, DataTable
- **overlays**: Dialog, Drawer, DetailList, Popover, CombineBar
- **navigation**: BrandMark, GroundworkMark, YshLockup, Topbar, AppShell
- **session**: Passbar, ParkingItem, CheckItem, OpLine, Heard, ReviewCard, ReviewOp, Recording, RuleTable
- **canvas**: BpmnEvent, BpmnTask, BpmnGateway, BpmnData, Lane, Pool, UnclearArea, Sticky, ContextNode, PaletteItem, PaletteGroup, FlowPick, SuggestBar

Every family maps to a class family in `groundwork/frontend/src/styles.css` or the starter shell. **Intentional additions**: `YshLockup` (wraps the website logo PNG so apps can show the YSH brand on navy), and `AppShell` as a React component (the starter defines it only as static HTML).

## Content fundamentals

From `groundwork/CLAUDE.md`: "Plain words, sentence case, active voice, Australian spelling. Name things the way staff would. Errors say what happened and what to do next. No em dashes."

- **Voice**: warm, direct, a colleague asking for help. "We" is the business or the project team; "you" is the staff member. First person appears in option labels written from the user's side ("How I actually do it").
- **Name things as staff would**: "Share files" not "Upload artifacts"; "Process maps"; "Person does it", "Done by hand", "System does it"; "Outside party" for a BPMN pool; "To confirm" for open questions; "Unclear area" for an ad hoc sub-process.
- **Headings are questions or plain statements**: "Hi Sam. What does your week actually involve?", "Which part of the work do these belong to?", "Do they contain personal information about tenants, borrowers or staff?"
- **Reassure and lower the bar**: "Rough is fine. Unofficial is especially welcome." "Not sure: That's fine. We'll work it out together." "Your first file is the most useful one, because it shows us where to look next."
- **Placeholders give a real example**: "For example: I update this every Monday from the bank statement, then email it to Dean."
- **Status words are human**: Waiting, Reading, Read, Needs a look, Blocked; pipeline "Finding people and things", "Searchable", "Couldn't be read".
- **Errors**: say what happened and the fix. "Answer the personal information question so we know how to handle these files." "The malware check flagged this file, so it can't be downloaded."
- **Buttons**: verb first, specific, with counts: "Email me a sign-in link", "Share 3 files", "Open the canvas", "Accept all 2 map changes". Progress uses an ellipsis: "Sending link…".
- **Privacy is stated plainly**, never hidden: "We store these files on the office server and keep them out of cloud AI."
- **Casing**: sentence case everywhere, including nav and buttons. The only uppercase is the small eyebrow label from the starter and the website's "PROPERTY" lockup.
- **Emoji**: never. Unicode glyphs appear only as functional marks: "•" (panel has a proposal), "●" (recording), "×" "+" "○" in gateways, "~" in unclear areas, "·" as a separator and as zero in tables.
- **Website tone** (ysh.com.au) is more promotional ("Satisfaction beyond the keys", "raising the bar", "stress-free"). Internal apps do not borrow that register; they borrow its warmth and its focus on tenants and owners.

## Visual foundations

- **Concept**: a drafting table. Survey-blue linework on cool paper, marker-yellow notes, boundary red for anything touching personal information (Groundwork's own description). The YSH brand navy (#1a2c3a) sits almost exactly on Groundwork's ink (#1c2b36), so the two read as one family; brand gold (#af9360) is reserved for brand moments (logo lockups, the thumbnail), not UI state.
- **Colour use**: surfaces are paper (#f6f8f7) and white panels. One accent, survey blue #2c5f8a, for primary buttons, links, active nav, focus and selection (#e3ecf4 soft fill). Green #3f7d5a = done / start events / detail pass / rule outputs. Marker #f2cf3e = sticky notes, chips, pending changes. Boundary #b3412e = personal info, errors, issues, risks. Workaround ochre (#fdf3cf fill, #b8931d edge, #8a6d12 text).
- **Type**: one face, Atkinson Hyperlegible (chosen for legibility "because every staff member, not just the keen ones, needs to find this easy"). Body 17px/1.55, h1 2.1rem bold tight, h2 1.3rem, h3 1.05rem, lede 1.12rem, quiet text 0.92em muted. Line length capped (68ch body, 24ch h1). Montserrat appears only in brand lettering, as a stand-in.
- **Spacing**: rem steps 0.2 / 0.4 / 0.6 / 0.8 / 1 / 1.2 / 1.5 / 2 / 2.5 / 3. Pages pad `2.5rem clamp(1rem,4vw,3rem) 5rem`, max 1100px. Generous vertical rhythm between form steps (2.2rem).
- **Backgrounds**: flat paper. The one pattern is the 40px drafting grid (white 8% lines on survey blue on the sign-in panel; #dce3e8 lines on the canvas). Hatching (135° stripes) marks "To confirm"; vertical stripes mark outside-party pools. No gradients, no photography in the apps, no illustrations beyond the FlowSketch line drawing on sign-in.
- **Borders**: 1.5px #c9d3da on every panel, input and button; 1px hairlines between rows; 2px ink for BPMN shapes. Emphasis edges are thick solid borders on one side: 6px survey left edge on home doors, 6px top edge on the Start-a-map card, 5px left edge on pass bars, 3px left rules on parking-lot and check items (coloured by category).
- **Radii**: 4px on controls and file cards, 10px on cards, dialogs, drop zone, tiles and BPMN tasks, 999px on status pills and person nodes.
- **Cards**: white, 1.5px line border, 10px radius, no shadow.
- **Shadows**: almost none. Only things that float get one: popovers `0 6px 18px rgba(28,43,54,.15)`, the combine bar `0 6px 24px …18`, and the sticky note's hard `0 2px 0` underline.
- **Hover**: outline buttons and cards change border to survey blue; primary buttons darken to #234d71; table rows and palette items fill survey-soft. No lift, no scale.
- **Press / selected**: survey-soft fill + survey border + bold (`.on`); segmented selection fills solid survey with white bold text. Nav active = 3px survey underline and bold.
- **Focus**: 3px solid survey outline offset 2px; inputs get a survey border plus a 3px survey-soft ring.
- **Disabled**: 55% opacity, not-allowed cursor.
- **AI states**: suggested elements are dashed survey blue until kept; pending changes get a 3px #fbe9a6 halo; a tiny survey (new) or dark ochre (change) bar sits above with Keep/Drop or Accept/Reject.
- **Motion**: minimal. The recording dot pulses (1.6s opacity). Canvas `fitView` pans over 300ms. Everything is disabled under `prefers-reduced-motion`.
- **Transparency and blur**: the dialog scrim is ink at 45%; lanes use survey-soft at 35%; the starter header uses 94% panel with a 0.75rem backdrop blur. Nothing else is translucent.
- **Layout**: sticky white top bar; map pages are a full-height grid (172px palette, canvas, 320–400px side panel). The starter uses a 3.5rem header, 15rem side nav and a 3-item bottom nav below 48rem.
- **Imagery (website only)**: daylight interiors of YSH developments: timber, stone, dark joinery, plants; warm and natural, no filters. Staff portraits on the team page.

## Iconography

- Groundwork uses **no icon font and no icon library**. Meaning is carried by shape and line style, BPMN-fashion.
- The only drawn icons are four 16px task markers (person, system cog, rule table, hand) in `canvas/nodes.tsx`, copied to `assets/icons/task-*.svg` along with the data object and data store shapes. They render in survey blue at 15px in a task's top-left corner.
- Palette items use **CSS glyphs**: 20×16 bordered boxes restyled per element (circle, thick ring, diamond, dashed, thick left edge, yellow fill). See `.gw-glyph` in `tokens/canvas.css`.
- The Groundwork mark (start circle → line → filled task box) is inline SVG in `Shell.tsx`; copied to `assets/logo/groundwork-mark.svg` and the `GroundworkMark` component.
- Unicode is used functionally (× + ○ ~ • ● ·), never emoji.
- If a future screen truly needs UI icons, pick a thin-stroke set (1.3–1.5px at 16px, round caps, like Lucide) and flag it; none is in the source today.

## Brand assets and substitutions

- `assets/logo/ysh-logo-white.png` (white YSH PROPERTY, transparent), `ysh-logo-white-boxed.png` (boxed variant), `ysh-logo-og.png` (white, from the site header), `ysh-favicon-navy.png` (navy square, white YSH, gold PROPERTY). All are small rasters fetched from ysh.com.au; no vector logo was provided.
- **Font substitution**: the YSH wordmark face is unknown. Montserrat (Google Fonts) stands in for brand lettering only. Atkinson Hyperlegible is the real Groundwork font, self-hosted from Google Fonts.
