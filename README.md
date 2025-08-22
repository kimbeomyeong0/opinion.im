# OPINION.IM - 뉴스 크롤링 프로젝트

## 📁 프로젝트 구조

```
OPINION.IM/
├── 📰 crawlers/              # 뉴스 크롤러 모듈들
│   ├── major_news/          # 주요 언론사 (조선, 동아, 한겨레 등)
│   ├── broadcasting/        # 방송사 (MBC 등)
│   ├── online_news/         # 온라인 언론사 (오마이뉴스, 프레시안)
│   ├── advanced_crawler.py  # 고급 크롤러
│   └── news_crawler.py      # 기본 뉴스 크롤러
├── ⚙️ config/                # 설정 파일들
├── 🐛 debug/                 # 디버그 HTML 파일들
├── 📚 docs/                  # 문서 및 마크다운 파일들
│   ├── analysis/            # HTML 구조 분석 문서
│   ├── guides/              # 사용 가이드
│   └── api/                 # API 문서
├── 📜 scripts/               # 실행 스크립트들
├── 🧪 tests/                 # 테스트 코드들
│   ├── unit/                # 단위 테스트
│   ├── integration/         # 통합 테스트
│   └── debug/               # 디버그 테스트
├── 🛠️ utils/                 # 유틸리티 모듈들
│   └── legacy/              # 레거시 파일들
├── 📊 data/                  # 데이터 저장소
├── 📝 logs/                  # 로그 파일들
├── 🗂️ temp/                  # 임시 파일들
└── requirements.txt          # Python 의존성
```

## 🚀 주요 기능

- **다양한 언론사 지원**: 조선일보, 동아일보, 한겨레, 중앙일보, 경향신문, 문화일보, 세계일보, MBC, 오마이뉴스, 프레시안 등
- **정치 기사 크롤링**: 각 언론사의 정치 섹션 기사 수집
- **편향성 분석**: 언론사별 정치 성향 분석 및 비교
- **Supabase 연동**: 데이터베이스 저장 및 관리
- **모듈화된 구조**: 언론사별 독립적인 크롤러

## 📋 사용법

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 크롤러 실행
```bash
# 조선일보 정치 기사 크롤링
./scripts/run_chosun_politics.sh

# 전체 크롤러 실행
./scripts/run_crawler.sh
```

## 🔧 설정

- `config/config.py`: 기본 설정
- `config/config_chosun.py`: 조선일보 전용 설정

## 📚 문서

- `docs/guides/README_chosun_politics.md`: 조선일보 크롤러 상세 설명
- `docs/analysis/`: HTML 구조 분석 문서들

## 🧪 테스트

```bash
# 전체 테스트 실행
python -m pytest tests/

# 특정 테스트 실행
python -m pytest tests/unit/
python -m pytest tests/debug/
```

## 🛠️ 개발

- `tests/debug/`: 디버깅 및 테스트 파일들
- `utils/supabase_manager_unified.py`: 통합된 Supabase 매니저 (권장)
- `utils/legacy/`: 레거시 Supabase 매니저들

## 📊 언론사 편향성 분포

- **보수 성향**: 조선일보, 동아일보, 문화일보, 세계일보
- **진보 성향**: 한겨레, 경향신문, 프레시안
- **중도 성향**: 중앙일보, MBC
- **시민 참여형**: 오마이뉴스
