# BHSA clause atom mother candidate site

BHSA clause atom의 mother candidate를 점검하는 정적 사이트와 Python 데이터 빌드 파이프라인입니다. 핵심 엔진은 [`bhsa_mother_candidate_skeleton_v5.py`](./bhsa_mother_candidate_skeleton_v5.py) 에 있고, 사이트는 `site/` 아래의 정적 파일을 GitHub Pages로 배포합니다.

## 구조

- `site/`: GitHub Pages에 배포되는 정적 UI
- `scripts/build_site_data.py`: BHSA/Text-Fabric를 이용해 `site/data/`용 정적 JSON 데이터를 생성
- `scripts/build_bhsa_static_site.py`: 정적 UI와 데이터를 함께 하나의 배포 디렉토리로 조립
- `bhsa_static_site_builder.py`: 제품용 데이터 스키마와 정적 사이트 빌드 로직
- `.github/workflows/pages.yml`: Pages 배포 워크플로
- `.github/workflows/build-site-data.yml`: 수동 데이터 빌드 워크플로

## 로컬 실행

환경 준비:

```bash
bash setup_bhsa_env.sh .venv-bhsa
source .venv-bhsa/bin/activate
```

정적 데이터 생성:

```bash
python scripts/build_site_data.py --outdir site/data
```

synthetic fixture로 전체 정적 사이트를 빠르게 조립:

```bash
python scripts/build_bhsa_static_site.py dist --synthetic --fit --top-k 3
```

로컬 미리보기:

```bash
python -m http.server --directory site 8000
```

브라우저에서 `http://localhost:8000` 을 열면 됩니다.

`dist/`로 조립했다면 다음처럼 바로 확인할 수 있습니다.

```bash
python -m http.server --directory dist 8000
```

## GitHub Pages 배포

`main` 브랜치에 push하면 `.github/workflows/pages.yml` 이 실행되고, `site/` 아래 정적 파일과 `site/data/` 에 생성된 JSON을 함께 Pages로 배포합니다.

## 수동 데이터 빌드

`Actions` 탭에서 `build-site-data` 워크플로를 수동 실행하면, BHSA 데이터로 생성한 정적 JSON 아티팩트를 내려받을 수 있습니다. 이 워크플로는 배포 없이 데이터만 검증하거나 재생성할 때 사용합니다.
