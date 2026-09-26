# The YSH Internal Apps Design System in Groundwork

Groundwork's interface uses the YSH Internal Apps Design System. The design system was built from
Groundwork's own styles, so adopting it changed little on screen. What it added is a token layer,
typed components and a class namespace (`gw-`) shared with the internal business app starter and
Excel to web app.

## Where things are

| Path | What it is |
|---|---|
| `frontend/design-system/` | Vendored snapshot: tokens, fonts, logos, task icons, and the component `.jsx`/`.d.ts` files as reference. Never edit it; see `SNAPSHOT.md`. |
| `frontend/src/ui/` | Typed ports of the components, one file per design-system family. Screens import from `../ui`. |
| `frontend/src/styles.css` | Only what the design system doesn't cover (page layout, the board grid, React Flow overrides, panel pieces), in `gw-` classes on tokens. Also a short list of fixes to design-system components. |
| `frontend/eslint.config.js` | Adherence rules, translated from the snapshot's `_adherence.oxlintrc.json`, plus a rule that screens use `src/ui` controls. |
| `frontend/src/test/styles.test.ts`, `ui.test.tsx` | No hex in `styles.css`; every `gw-` class used is defined; component markup. |

`main.tsx` imports React Flow's styles, then `design-system/styles.css`, then `src/styles.css`.
Fonts are self-hosted from the snapshot, so staff browsers no longer call Google Fonts.

## Decisions (2026-09-26)

- Classes use the design system's `gw-` namespace. Blocks are prefixed (`gw-card`); modifiers
  are not (`gw-card`'s `on`, `pk-issue`, `pass-detail`), following the design system.
- The YSH Property logo appears on the sign-in story panel beside the Groundwork mark, and the
  navy YSH favicon is the tab icon. The app itself stays Groundwork-branded; gold stays out of the
  interface.
- No new dependencies.

## Components

Ported to `src/ui`: Button (plus LinkButton), SegToggle, Status, Tag, Chip; Field, Input, Select,
TextArea, Check, Segmented, OptionGroup, DropZone; Card, Door, Doors, FileCard, Tiles, Rows,
Table, DataTable; Dialog, Drawer, DetailList, Popover, CombineBar; GroundworkMark, BrandMark,
YshLockup, Topbar; Passbar, ParkingItem, CheckItem, OpLine, Heard, ReviewCard, ReviewOp,
Recording; PaletteItem, PaletteGroup, FlowPick, SuggestBar.

Not ported:
- AppShell and the `ibs-` shell: for the starter app. Groundwork keeps its top bar.
- RuleTable: display only. The Rules panel edits tables, so it uses the `gw-ruletable` classes
  with `Table` and `Input`.
- BpmnEvent, BpmnTask, BpmnGateway, BpmnData, Lane, Pool, UnclearArea, Sticky, ContextNode: the
  canvas needs React Flow nodes with handles, resizers and editable labels. `canvas/nodes.tsx`
  draws them with the same classes.

Additions to the design system's APIs: `LinkButton`, `Input`/`Select`/`TextArea`, `Table`,
`artifactTone()`, a `to` prop on Door (router link), `small` on Tiles items, `note` and `extra`
on ReviewCard, `stopDisabled` on Recording, `removeLabel` on Chip, `label` on Drawer and Popover.

## What changed on screen

Checked by comparing every element's computed style on each page and board panel, before and
after, with the same seeded data. Everything else is identical.

- Top-bar links and buttons no longer wrap; the top-bar nav wraps as a whole on narrow screens.
- Checkboxes and radios are survey blue.
- Drawer titles sit level with the Close link instead of 2rem lower.
- BPMN task and context-element text is tighter (line height 1.3), and task markers are bolder.
- Context elements (person, system, issue and the rest) and unclear areas now show the selection
  halo and the dashed "suggested" edge like steps do.
- Joined toggle buttons (board panels) no longer double their borders.
- Coverage: process rows read in ink, and sub-process names are regular weight.
- Rule-table headers are slightly smaller and muted.
- Tables only look clickable (pointer, hover fill) when a row opens something.
- The sign-in panel shows the YSH Property logo; the tab icon is the YSH favicon.

## Behaviour added

- Dialogs trap Tab, close on Escape when they can be dismissed, and return focus when they close.
- Drawers and the Layers popover close on Escape and return focus to what opened them.
- Clickable table rows open with Enter or Space.
- Buttons default to `type="button"`, so only an explicit submit button submits a form.

## Fixes to raise upstream

These are fixed in Groundwork (`src/ui`, `src/styles.css`); the design system should take them.

- `.gw-table tbody tr` gets a pointer cursor and hover fill on every table. It should apply only to
  clickable rows; `DataTable` should add Enter and Space handling to the `tabIndex` it sets.
- `Dialog` and `Drawer` have no Escape, focus trap or focus return.
- `.gw-suggested` sets `border-style` without a width, so on an element with no border (the event
  and gateway wrappers `BpmnEvent` and `BpmnGateway` put it on, and `.gw-sticky`) it draws a 3px
  (medium) border. Groundwork puts the class on the ring or diamond and sets the sticky's width.
- `.gw-flowpick` lost the app's `:focus-within` outline, so the connector picker had no visible
  focus.
- `Heard`, `CombineBar`, `DataTable`'s caption, `Sticky`, `BrandMark` (`big`) and `YshLockup`
  (`onDark={false}`) use inline styles, some with px values, against the design system's own
  adherence rules.
- `Topbar` uses `href="#"` links.
- `.gw-rows` has no narrow-screen layout; Groundwork keeps its single-column rule under 640px.
- In `.gw-seg-toggle`, the selected button loses its left survey edge because every button after
  the first drops its left border.
- `fonts/Montserrat-500`, `-600` and `-700` are the same file.

## Not done

- DOM-level tests of the keyboard behaviour (Escape, focus trap, focus return) need `jsdom` or
  similar, a new dev dependency. The behaviour was checked by hand in the browser.
- The Groundwork UI kit shows a "Turn into a web app" button in Library. That belongs to Excel to
  web app and is out of scope here (see `CLAUDE.md`, Purpose).
