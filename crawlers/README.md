# Crawlers

뉴스 크롤링을 위한 모듈들입니다.

## 📁 파일 목록

- `advanced_crawler.py` - 고급 크롤러 (기본 크롤러 확장)
- `news_crawler.py` - 기본 뉴스 크롤러
- `*_politics_crawler.py` - 각 언론사별 정치 기사 크롤러

## 🏢 지원 언론사

- 조선일보 (`chosun_politics_crawler.py`)
- 동아일보 (`donga_politics_crawler.py`)
- 한겨레 (`hani_politics_crawler.py`)
- 중앙일보 (`joongang_politics_crawler.py`)
- 경향신문 (`khan_politics_crawler.py`)
- 문화일보 (`kmib_politics_crawler.py`)
- MBC (`mbc_politics_crawler.py`)
- 세계일보 (`segye_politics_crawler.py`)
- 오마이뉴스 (`ohmynews_politics_crawler.py`)
- 프레시안 (`pressian_politics_crawler.py`)

## 🔧 사용법

각 크롤러는 독립적으로 실행할 수 있으며, 공통 인터페이스를 따릅니다.
