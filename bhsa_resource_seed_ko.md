# ETCBC/BHSA 공식 seed 리소스 메모

## 이번 버전에서 추가된 것

- `:official_seed` 내장 리소스
- `seed-resources` 명령
- opening conjunction / opening preposition class를 evidence로 쓰는 feature
- `infinitive_preposition_classes` 필드

## 바로 쓰는 방법

```bash
python bhsa_mother_candidate_skeleton_v3.py seed-resources resource_tables_official_seed.json \
  --md-out resource_seed_notes.md
```

파일을 만들지 않고 바로 내장 seed를 쓰려면:

```bash
python bhsa_mother_candidate_skeleton_v3.py eval \
  --resources :official_seed \
  --json-out eval.json \
  --md-out eval.md
```

## 해석 원칙

이 seed는 두 층으로 나뉜다.

1. **공식 문서에 직접 근거가 있는 항목**
   - `conjunction_classes`
   - `preposition_classes`
   - `infinitive_preposition_classes`
   - `relative_lexemes`의 `>CR`

2. **조심스럽게 넣은 시작점 heuristic**
   - `quote_verbs`
   - `object_clause_governors`

즉 이 파일은 **ETCBC 원형을 복원한 완제품**이 아니라, 공식자료 기반의 안전한 시작점이다.

## 실무 권장 순서

1. `:official_seed` 또는 `resource_tables_official_seed.json`으로 시작
2. `fit`으로 `arg_weights` 학습
3. `eval` / `ablate`로 feature 효율 확인
4. 오탐 사례를 보고 lexeme table을 보수적으로 확장

## 주의

현재 v3는 `infinitive_preposition_classes`를 저장하지만, 아직 scoring feature에 직접 쓰지는 않는다.
이건 다음 단계에서 infinitive construct 계열 feature를 추가하기 위한 정렬 작업이다.
