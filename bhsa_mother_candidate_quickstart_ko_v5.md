# BHSA mother candidate v5 빠른 시작

## 1) 환경 준비

```bash
bash setup_bhsa_env.sh .venv-bhsa
source .venv-bhsa/bin/activate
```

## 2) 전체 파이프라인 실행

```bash
bash run_bhsa_pipeline_v5.sh outputs_v5 :official_seed
```

생성 파일:

- `outputs_v5/weights.json`
- `outputs_v5/eval.json`, `outputs_v5/eval.md`
- `outputs_v5/ablate.json`, `outputs_v5/ablate.md`
- `outputs_v5/diagnose.json`, `outputs_v5/diagnose.md`
- `outputs_v5/mine.json`, `outputs_v5/mine.md`
- `outputs_v5/mined_patch.json`

## 3) resource 확장 후보만 따로 뽑기

```bash
python bhsa_mother_candidate_skeleton_v5.py mine \
  --resources weights.json \
  --min-count 2 \
  --json-out mine.json \
  --md-out mine.md \
  --patch-out mined_patch.json
```

`mine.md`는 자동 병합 가능한 항목과 수동 검토가 필요한 항목을 분리해서 보여준다.

- 자동 병합 기본 대상: `relative_lexemes`, 각종 governor set
- 수동 검토 대상: `opening conjunction/preposition class`
- `quote_verbs`는 기본적으로 리포트만 하고, `--apply-quote-verbs`를 줘야 patch에 합쳐진다.
