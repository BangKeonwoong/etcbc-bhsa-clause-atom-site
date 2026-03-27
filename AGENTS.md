# BHSA UI Design Rules

These rules apply to all Figma-driven or hand-authored UI work in this repository.

## Project Shape

- The shipped UI is a framework-free static site under `site/`.
- Data is loaded from `site/data/catalog.json` and `site/data/atoms/<id>.json`.
- If the data schema changes, update the Python builder, tests, and UI together. Do not silently drift the front end away from the generated JSON contract.

## Visual Direction

- Treat the product as a research instrument, not a SaaS dashboard.
- Favor a strong editorial or archival-lab feel: dark shell, warm folio surfaces, sharp sectioning, visible hierarchy.
- The first viewport must immediately show three things:
  - how to navigate
  - which atom is selected
  - what the model currently believes
- Avoid generic card grids, pastel glassmorphism, purple gradients, and neutral enterprise layouts.

## Typography And Tokens

- Display type should feel deliberate; current direction uses `Fraunces` for titles.
- UI text should remain dense and readable; current direction uses `IBM Plex Sans`.
- Numeric/data labels should use a monospaced face; current direction uses `IBM Plex Mono`.
- Keep all colors, radii, shadows, spacing, and motion values in `:root` CSS custom properties.
- Do not hardcode one-off colors inside component rules unless there is no reusable token for that case.

## Layout Rules

- Preserve a three-zone reading model on desktop:
  - left `book ledger`
  - center `focus folio`
  - right `candidate board`
- The center column is the primary stage. The selected clause text must carry the strongest visual weight.
- Phrase structure and predicate metadata belong below the main text, not buried in the side rails.
- Candidate evidence must remain scannable at a glance; use compact ribbons, chips, or meters instead of long prose.

## Interaction Rules

- `book-select`, `atom-input`, previous/next navigation, and URL syncing are required behavior.
- Candidate cards may link directly to the candidate mother atom when that atom exists in the current dataset.
- Preserve clear empty, loading, and missing-data states.
- Mobile should collapse into a single column without hiding critical evidence or navigation.

## Figma Workflow

- Figma MCP is configured as a project tool. When it is available in the active session, use it before implementing major UI changes.
- For Figma-to-code work, fetch design context and screenshot context first, then translate into this repository's static HTML/CSS/JS architecture.
- Treat generated Figma code as design reference, not as final production code style.
- The final source of truth for implementation remains:
  - `site/index.html`
  - `site/styles.css`
  - `site/app.js`

## File Ownership

- HTML structure and semantic regions live in `site/index.html`.
- Visual language, tokens, and responsive behavior live in `site/styles.css`.
- Data loading, state, and rendering logic live in `site/app.js`.
- Design rationale and future redesign guidance should be written to `design/` rather than hidden in commit messages.
