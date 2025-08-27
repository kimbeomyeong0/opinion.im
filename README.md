# OPINION.IM

한국 주요 언론사의 정치 기사를 수집하고 분석하는 뉴스 크롤링 프로젝트입니다.

## 🏗️ 프로젝트 구조

```
/opinion.im
  /crawlers              → 크롤러 모음
    /major_news         → 주요 언론사 크롤러 (17개)
    /online_news        → 온라인 매체 크롤러 (2개)
    /broadcasting       → 방송사 크롤러 (1개)
    README.md           → 크롤러 목록 및 실행법
  /common               → 공통 모듈
    supabase_manager.py → DB 저장 및 조회
    parser_utils.py     → HTML 파싱, 광고/기자명 제거
    logger.py           → 로깅 유틸리티
    config.py           → 환경변수 및 상수값 관리
  /scripts              → 실행 스크립트
    run_all.py          → 모든 크롤러 실행
    run_sequential.py   → 순차 실행
    check_articles_count.py
    check_missing_media.py
    debug_*.py          → 디버깅 도구
  /tests                → 테스트 코드
    test_basic.py       → 기본 기능 테스트
    test_*.py           → 개별 크롤러 테스트
  /docs                 → 문서
    crawler_guide.md    → 새 크롤러 추가 가이드
  /data                 → 수집된 JSON 캐시
  /logs                 → 실행 로그
  requirements.txt      → Python 의존성
  README.md             → 이 파일
```

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 저장소 클론
git clone https://github.com/your-username/opinion.im.git
cd opinion.im

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경변수 설정

`.env` 파일을 생성하고 Supabase 정보를 설정하세요:

```bash
# .env
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
MAX_WORKERS=8
TIMEOUT=10
MAX_RETRIES=3
DELAY_BETWEEN_REQUESTS=0.1
```

### 3. 크롤러 실행

```bash
# 모든 크롤러 실행 (병렬)
python scripts/run_all.py

# 순차 실행
python scripts/run_sequential.py

# 개별 크롤러 실행
python crawlers/major_news/chosun_politics_crawler.py
```

## 📰 지원 언론사

### 주요 언론사 (17개)
- **종합일간지**: 조선일보, 동아일보, 한겨레, 중앙일보, 경향신문, 국민일보, 문화일보, 세계일보
- **경제일간지**: 한국경제, 매일경제, 서울경제
- **통신사**: 연합뉴스, 뉴스1, YTN
- **방송사**: KBS, SBS, JTBC

### 온라인 매체 (2개)
- 오마이뉴스, 프레시안

### 방송사 (1개)
- MBC

## 🔧 주요 기능

### 공통 모듈
- **로깅 시스템**: 일관된 로그 형식과 파일 저장
- **HTML 파싱**: 광고 제거, 기자명 추출, 텍스트 정리
- **데이터베이스 관리**: Supabase 연동, 중복 방지
- **설정 관리**: 환경변수 및 상수값 중앙 관리

### 크롤러 기능
- **자동 발견**: 디렉토리 기반 크롤러 자동 로드
- **병렬 실행**: ThreadPoolExecutor를 사용한 동시 실행
- **에러 처리**: 네트워크 오류, 파싱 오류 등에 대한 견고한 처리
- **결과 요약**: 실행 결과 및 통계 정보 제공

## 📊 실행 결과 예시

```
2025-01-27 10:30:15 - opinion_crawler.run_all - INFO - 모든 크롤러 실행 시작
2025-01-27 10:30:15 - opinion_crawler.run_all - INFO - 발견된 크롤러: {'major_news': ['chosun', 'donga', ...], 'online_news': ['ohmynews', 'pressian']}
2025-01-27 10:30:15 - opinion_crawler.run_all - INFO - 총 20개 크롤러 실행 예정
2025-01-27 10:30:16 - opinion_crawler.chosun_crawler - INFO - 크롤러 시작: 조선일보
2025-01-27 10:30:18 - opinion_crawler.chosun_crawler - INFO - 기사 파싱 성공: 대통령, 정치 개혁 강조...
2025-01-27 10:30:19 - opinion_crawler.chosun_crawler - INFO - 크롤러 완료: 수집: 15개, 저장: 12개, 소요시간: 3.45초
...
2025-01-27 10:35:20 - opinion_crawler.run_all - INFO - ============================================================
2025-01-27 10:35:20 - opinion_crawler.run_all - INFO - 크롤러 실행 결과 요약
2025-01-27 10:35:20 - opinion_crawler.run_all - INFO - ============================================================
2025-01-27 10:35:20 - opinion_crawler.run_all - INFO - 총 크롤러 수: 20
2025-01-27 10:35:20 - opinion_crawler.run_all - INFO - 성공한 크롤러 수: 18
2025-01-27 10:35:20 - opinion_crawler.run_all - INFO - 실패한 크롤러 수: 2
2025-01-27 10:35:20 - opinion_crawler.run_all - INFO - 총 수집 기사 수: 245
2025-01-27 10:35:20 - opinion_crawler.run_all - INFO - 총 저장 기사 수: 198
2025-01-27 10:35:20 - opinion_crawler.run_all - INFO - 총 소요 시간: 305.67초
```

## 🧪 테스트

```bash
# 기본 기능 테스트
python tests/test_basic.py

# 특정 크롤러 테스트
python tests/test_chosun_crawler.py

# 모든 테스트 실행
python -m unittest discover tests/
```

## 📝 새 크롤러 추가

새로운 언론사 크롤러를 추가하려면 [크롤러 가이드](docs/crawler_guide.md)를 참조하세요.

## 🔍 디버깅 도구

```bash
# HTML 구조 확인
python scripts/debug_html.py

# 데이터베이스 상태 확인
python scripts/debug_database.py

# 수집된 기사 개수 확인
python scripts/check_articles_count.py

# 미디어 파일 누락 확인
python scripts/check_missing_media.py
```

## 📋 요구사항

- Python 3.8+
- Supabase 계정 및 프로젝트
- 인터넷 연결

## 📦 의존성

주요 패키지:
- `requests`: HTTP 요청
- `beautifulsoup4`: HTML 파싱
- `supabase`: 데이터베이스 연동
- `python-dotenv`: 환경변수 관리

전체 의존성은 `requirements.txt`를 참조하세요.

## 🤝 기여하기

1. 이 저장소를 포크하세요
2. 기능 브랜치를 생성하세요 (`git checkout -b feature/amazing-feature`)
3. 변경사항을 커밋하세요 (`git commit -m 'Add amazing feature'`)
4. 브랜치에 푸시하세요 (`git push origin feature/amazing-feature`)
5. Pull Request를 생성하세요

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 `LICENSE` 파일을 참조하세요.

## 📞 문의

프로젝트에 대한 문의사항이나 버그 리포트는 [Issues](../../issues)를 통해 제출해주세요.

## 🙏 감사의 말

이 프로젝트는 한국의 다양한 언론사들이 제공하는 뉴스 콘텐츠를 기반으로 합니다. 각 언론사들의 노고에 감사드립니다.
