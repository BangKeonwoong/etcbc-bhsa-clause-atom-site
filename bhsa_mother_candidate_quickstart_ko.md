# BHSA mother candidate prototype 빠른 실행

## 1) 환경 준비

```bash
bash setup_bhsa_env.sh .venv-bhsa
source .venv-bhsa/bin/activate
```

## 2) 기본 리소스 파일 복사

```bash
cp resource_tables_template.json my_resources.json
```

그 다음 `quote_verbs`, `object_clause_governors`, `subject_clause_governors`,
`predicative_clause_governors`, `conjunction_classes`, `preposition_classes`,
`relative_lexemes`를 연구 목적에 맞게 채운다.

## 3) 전체 파이프라인 실행

```bash
bash run_bhsa_pipeline.sh outputs my_resources.json
```

생성 파일:

- `outputs/weights.json`
- `outputs/eval.json`
- `outputs/eval.md`
- `outputs/ablate.json`
- `outputs/ablate.md`
- `outputs/predictions.jsonl`

## 4) 실제 코퍼스 없이 스모크 테스트

```bash
python bhsa_mother_candidate_synthetic_smoke.py
python -m unittest test_bhsa_mother_candidate_v2.py
```

이 테스트는 가짜 TF/BHSA API 위에서 다음을 확인한다.

- candidate pool 생성
- rightward 무허가 후보 0점 처리
- gold edge 기반 weight fitting
- eval 지표 계산
- prediction export

## 5) 자주 보는 옵션

```bash
python bhsa_mother_candidate_skeleton_v2.py demo 12345 --resources weights.json --top-k 5
python bhsa_mother_candidate_skeleton_v2.py eval --resources weights.json --json-out eval.json --md-out eval.md
python bhsa_mother_candidate_skeleton_v2.py ablate --resources weights.json --json-out ablate.json --md-out ablate.md
```

## 6) 주의

- `instruction` pool은 ETCBC 스타일 pruning에 더 가깝다.
- `tab_only`는 더 느슨한 스트레스 테스트용이다.
- synthetic smoke는 로직 검증용이고, 성능 수치는 실제 BHSA 환경에서 다시 봐야 한다.
