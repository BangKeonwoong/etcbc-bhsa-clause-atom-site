# BHSA mother candidate prototype usage (v3)

## New in v3

- Built-in ETCBC-style starter resources via `:official_seed`
- `seed-resources` command to write a starter JSON plus notes
- Opening-class evidence features:
  - `OpeningConjunctionClassFeature`
  - `OpeningPrepositionClassFeature`
- Resource schema now includes `infinitive_preposition_classes`

## Fastest start

Write the starter resource table:

```bash
python bhsa_mother_candidate_skeleton_v3.py seed-resources resource_tables_official_seed.json \
  --md-out resource_seed_notes.md
```

Use the built-in seed directly without writing a file:

```bash
python bhsa_mother_candidate_skeleton_v3.py eval \
  --resources :official_seed \
  --json-out eval.json \
  --md-out eval.md
```

Fit argument weights starting from the starter seed:

```bash
python bhsa_mother_candidate_skeleton_v3.py fit weights.json \
  --resources :official_seed
```

Inspect one clause atom:

```bash
python bhsa_mother_candidate_skeleton_v3.py demo 12345 \
  --resources weights.json \
  --top-k 5
```

## Notes

- `:official_seed` loads the built-in ETCBC/BHSA-style starter resource table.
- The starter table is mixed: some entries are directly grounded in published ETCBC/BHSA docs, and some are cautious heuristic starters.
- The conjunction/preposition class mappings are intended to support opening-class evidence and later code-class reconstruction.
- `infinitive_preposition_classes` is stored for ETCBC alignment even though the current prototype does not yet exploit that field directly in scoring.
