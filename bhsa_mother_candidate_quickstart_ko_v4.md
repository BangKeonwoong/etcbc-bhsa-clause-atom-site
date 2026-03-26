# BHSA mother candidate v4 빠른 실행

## 가장 빠른 순서

```bash
bash setup_bhsa_env.sh .venv-bhsa
source .venv-bhsa/bin/activate
bash run_bhsa_pipeline_v4.sh outputs_v4 :official_seed
```

이렇게 하면 아래 파일이 생성된다.

- `weights.json`
- `eval.json`, `eval.md`
- `diagnose.json`, `diagnose.md`
- `ablate.json`, `ablate.md`
- `predictions.jsonl`

## 개별 명령

평가:

```bash
python bhsa_mother_candidate_skeleton_v4.py eval \
  --resources :official_seed \
  --json-out eval.json \
  --md-out eval.md
```

진단:

```bash
python bhsa_mother_candidate_skeleton_v4.py diagnose \
  --resources :official_seed \
  --top-k 5 \
  --top-n 25 \
  --json-out diagnose.json \
  --md-out diagnose.md
```

가중치 학습:

```bash
python bhsa_mother_candidate_skeleton_v4.py fit weights.json \
  --resources :official_seed
```

단일 clause_atom 후보 보기:

```bash
python bhsa_mother_candidate_skeleton_v4.py demo 12345 \
  --resources weights.json \
  --top-k 5
```

## `diagnose`에서 바로 볼 것

- opening conjunction / preposition coverage
- relative-marker coverage
- `Objc / Subj / PreC` gold governor coverage
- gold `rela`별 hit@1, hit@3, MRR
- opening-class evidence가 gold pair에서 실제로 몇 번 켜지는지
- 자주 나오지만 resource table에 없는 lexeme 목록
