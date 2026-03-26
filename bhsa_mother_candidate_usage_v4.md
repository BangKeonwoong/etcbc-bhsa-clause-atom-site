# BHSA mother candidate prototype usage (v4)

## New in v4

- `diagnose` command for resource-table coverage and gold-evidence activation
- relation-slice evaluation by gold `rela`
- coverage audit for:
  - opening conjunction lexemes
  - opening preposition lexemes
  - relative-marker lexemes
  - gold object/subject/predicative clause governors
  - heuristic quote-governor candidates
- synthetic smoke and unittest coverage for the new diagnostics path
- `top_k=3` metric/rendering bug fixed in evaluation and diagnostics

## Fastest start

Run the built-in ETCBC-style seed directly:

```bash
python bhsa_mother_candidate_skeleton_v4.py eval \
  --resources :official_seed \
  --json-out eval.json \
  --md-out eval.md
```

Run diagnostics on the same seed:

```bash
python bhsa_mother_candidate_skeleton_v4.py diagnose \
  --resources :official_seed \
  --top-k 5 \
  --top-n 25 \
  --json-out diagnose.json \
  --md-out diagnose.md
```

Fit weights from BHSA gold and then diagnose the fitted model:

```bash
python bhsa_mother_candidate_skeleton_v4.py fit weights.json \
  --resources :official_seed

python bhsa_mother_candidate_skeleton_v4.py diagnose \
  --resources weights.json \
  --json-out diagnose.json \
  --md-out diagnose.md
```

Run the full v4 pipeline:

```bash
bash run_bhsa_pipeline_v4.sh outputs_v4 :official_seed
```

## What `diagnose` gives you

- overall baseline ranking summary
- per-`rela` slices: pool coverage, scored coverage, hit@1, hit@3, MRR, avg gold rank
- resource-table coverage for conjunction/preposition/relative lexemes
- gold-governor coverage for `Objc`, `Subj`, `PreC`
- gold-evidence coverage by label
- opening-class evidence activation on gold pairs
- top uncovered lexeme lists to guide resource-table expansion
