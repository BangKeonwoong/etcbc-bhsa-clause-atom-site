# BHSA mother candidate prototype usage

## Files

- `bhsa_mother_candidate_skeleton_v2.py`: current working prototype.
- `resource_tables_template.json`: starter resource table.

## Commands

Fit weights from the BHSA `mother` edge:

```bash
python bhsa_mother_candidate_skeleton_v2.py fit weights.json \
  --resources resource_tables_template.json
```

Evaluate the generator and write JSON + Markdown:

```bash
python bhsa_mother_candidate_skeleton_v2.py eval \
  --resources weights.json \
  --json-out eval.json \
  --md-out eval.md
```

Run leave-one-feature-out ablation:

```bash
python bhsa_mother_candidate_skeleton_v2.py ablate \
  --resources weights.json \
  --json-out ablate.json \
  --md-out ablate.md
```

Inspect one clause atom:

```bash
python bhsa_mother_candidate_skeleton_v2.py demo 12345 \
  --resources weights.json \
  --top-k 5
```

Export top-k predictions:

```bash
python bhsa_mother_candidate_skeleton_v2.py export predictions.jsonl \
  --resources weights.json \
  --top-k 5 \
  --format jsonl
```

## Notes

- `--pool-mode instruction` reproduces the stricter ETCBC-style pruning that uses final `instruction` state.
- `--pool-mode tab_only` removes that dependence and gives a cleaner stress test.
- The script compiles without Text-Fabric, but runtime commands require a TF/BHSA environment.
