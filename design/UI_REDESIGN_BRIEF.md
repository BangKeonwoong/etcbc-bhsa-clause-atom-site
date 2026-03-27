# BHSA Clause Atom Observatory

This redesign was shaped with the workflows from `frontend-skill`, `figma-use`, `figma-generate-design`, and `figma-create-design-system-rules`.

## Visual Thesis

The site should feel like a research table laid out for textual judgment:

- a dark outer shell that frames the work
- a warm folio stage for the selected clause atom
- a ranked evidence board for mother candidates

The goal is not "pretty dashboard polish." The goal is a reading environment where the clause text, relation signals, and ranking evidence become easier to judge quickly.

## Information Architecture

### 1. Command Layer

The top control surface must let a researcher change book, jump to an atom, and move sequentially without scrolling into the detail panes.

### 2. Book Ledger

The left rail is a ledger of clause atoms for the selected book. Each row should show:

- atom id
- section reference
- clause text snippet
- top prediction cue

This list is for orientation, not deep reading.

### 3. Focus Folio

The center column is the primary reading stage. It must show:

- selected atom id and location
- clause text with strong typographic weight
- gold mother
- top hypothesis
- compact clause profile markers

### 4. Clause Anatomy

Predicate information and phrase grouping should sit below the main text, organized into:

- predicate and verb morphology
- opening phrases
- preverbal phrases
- postverbal phrases
- leftover phrases not captured by those groups

### 5. Candidate Board

The right rail is a ranked mother-candidate board. Each entry should show:

- rank
- mother atom id
- score
- relation labels
- evidence tags

When possible, candidate cards should jump directly to the mother atom.

## Implementation Rules

- Keep the existing static JSON contract.
- Prefer structural sections over generic repeated cards.
- Use a restrained motion system:
  - subtle rise on hover
  - short entry motion for candidates
  - no decorative idle animation
- Let typography and contrast create emphasis before adding color.
- Treat evidence tags as the smallest unit of judgment, so they must remain compact and readable.
