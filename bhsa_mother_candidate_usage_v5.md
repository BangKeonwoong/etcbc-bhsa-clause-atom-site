# BHSA mother-candidate prototype v5

## New in v5

- `mine` subcommand added.
- Distinguishes **safe additions** from **manual review** candidates.
- Can emit a merged resource patch JSON.
- Quote verbs are reported, but only merged when `--apply-quote-verbs` is supplied.

## Commands

```bash
python bhsa_mother_candidate_skeleton_v5.py fit weights.json \
  --resources :official_seed
```

```bash
python bhsa_mother_candidate_skeleton_v5.py eval \
  --resources weights.json \
  --json-out eval.json \
  --md-out eval.md
```

```bash
python bhsa_mother_candidate_skeleton_v5.py diagnose \
  --resources weights.json \
  --json-out diagnose.json \
  --md-out diagnose.md
```

```bash
python bhsa_mother_candidate_skeleton_v5.py mine \
  --resources weights.json \
  --min-count 2 \
  --json-out mine.json \
  --md-out mine.md \
  --patch-out mined_patch.json
```

```bash
python bhsa_mother_candidate_skeleton_v5.py mine \
  --resources weights.json \
  --min-count 2 \
  --json-out mine.json \
  --md-out mine.md \
  --patch-out mined_patch_with_quote.json \
  --apply-quote-verbs
```

## Mine output shape

- `safe_additions.relative_lexemes`
- `safe_additions.object_clause_governors`
- `safe_additions.subject_clause_governors`
- `safe_additions.predicative_clause_governors`
- `safe_additions.quote_verbs`
- `manual_review.opening_conjunctions`
- `manual_review.opening_prepositions`

The `patch-out` file merges only the safe set additions by default. `quote_verbs` remain report-only unless the explicit flag is passed.
