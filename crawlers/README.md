# 크롤러 (Crawlers)

이 디렉토리는 다양한 언론사의 정치 기사를 수집하는 크롤러들을 포함합니다.

## 디렉토리 구조

```
/crawlers
  /major_news        → 주요 언론사 크롤러 모음
  /online_news       → 온라인 매체 크롤러 모음
  /broadcasting      → 방송사 크롤러 모음
  README.md          → 이 파일
```

## 크롤러 목록

### 주요 언론사 (Major News)

| 언론사 | 파일명 | 상태 | 설명 |
|--------|--------|------|------|
| 조선일보 | `chosun_politics_crawler.py` | ✅ | 종합일간지 |
| 동아일보 | `donga_politics_crawler.py` | ✅ | 종합일간지 |
| 한겨레 | `hani_politics_crawler.py` | ✅ | 종합일간지 |
| 한국경제 | `hankyung_politics_crawler.py` | ✅ | 경제일간지 |
| 중앙일보 | `joongang_politics_crawler.py` | ✅ | 종합일간지 |
| JTBC | `jtbc_politics_collector.py` | ✅ | 종합방송사 |
| KBS | `kbs_politics_api_collector.py` | ✅ | 공영방송사 |
| 경향신문 | `khan_politics_crawler.py` | ✅ | 종합일간지 |
| 국민일보 | `kmib_politics_crawler.py` | ✅ | 종합일간지 |
| 매일경제 | `mk_politics_crawler.py` | ✅ | 경제일간지 |
| 문화일보 | `munhwa_politics_crawler.py` | ✅ | 종합일간지 |
| 뉴스1 | `news1_politics_crawler.py` | ✅ | 통신사 |
| SBS | `sbs_politics_crawler.py` | ✅ | 종합방송사 |
| 서울경제 | `sedaily_politics_crawler.py` | ✅ | 경제일간지 |
| 세계일보 | `segye_politics_crawler.py` | ✅ | 종합일간지 |
| 연합뉴스 | `yna_politics_crawler.py` | ✅ | 통신사 |
| YTN | `ytn_politics_crawler.py` | ✅ | 종합방송사 |

### 온라인 매체 (Online News)

| 언론사 | 파일명 | 상태 | 설명 |
|--------|--------|------|------|
| 오마이뉴스 | `ohmynews_politics_crawler.py` | ✅ | 시민참여형 언론 |
| 프레시안 | `pressian_politics_crawler.py` | ✅ | 인터넷 언론 |

### 방송사 (Broadcasting)

| 언론사 | 파일명 | 상태 | 설명 |
|--------|--------|------|------|
| MBC | `mbc_politics_crawler.py` | ✅ | 종합방송사 |

## 실행 방법

### 1. 개별 크롤러 실행

```bash
# 조선일보 크롤러만 실행
python crawlers/major_news/chosun_politics_crawler.py

# 동아일보 크롤러만 실행
python crawlers/major_news/donga_politics_crawler.py
```

### 2. 모든 크롤러 실행

```bash
# 병렬 실행 (기본)
python scripts/run_all.py

# 순차 실행
python scripts/run_sequential.py
```

### 3. 특정 타입의 크롤러만 실행

```bash
# 주요 언론사만 실행
python scripts/run_major_news.py

# 온라인 매체만 실행
python scripts/run_online_news.py
```

## 크롤러 구조

각 크롤러는 다음과 같은 구조를 따릅니다:

```python
class ExamplePoliticsCrawler:
    def __init__(self):
        # 초기화: 로거, 파서, DB 매니저 설정
        
    def get_article_links(self):
        # 기사 목록 페이지에서 링크 수집
        
    def parse_article(self, url):
        # 개별 기사 파싱
        
    def save_articles(self, articles):
        # 데이터베이스에 저장
        
    def run(self):
        # 전체 크롤링 프로세스 실행
```

## 공통 모듈 사용

모든 크롤러는 공통 모듈을 사용합니다:

- **로거**: `common.logger.get_logger()`
- **파서**: `common.parser_utils.ParserUtils`
- **DB 관리**: `common.supabase_manager.SupabaseManager`
- **설정**: `common.config.config`

## 새 크롤러 추가

새로운 언론사 크롤러를 추가하려면 [크롤러 가이드](../../docs/crawler_guide.md)를 참조하세요.

## 주의사항

1. **에러 처리**: 모든 네트워크 요청과 파싱 작업에 적절한 예외 처리를 구현하세요.
2. **로깅**: 중요한 작업과 오류 상황을 로그로 남기세요.
3. **중복 방지**: 이미 수집된 기사는 다시 저장하지 않도록 중복 확인을 구현하세요.
4. **요청 제한**: 서버에 과부하를 주지 않도록 적절한 지연시간을 설정하세요.
5. **웹사이트 정책 준수**: robots.txt와 크롤링 정책을 확인하고 준수하세요.

## 문제 해결

### 일반적인 문제들

1. **Import 오류**: `sys.path.append()`를 사용하여 프로젝트 루트를 Python 경로에 추가하세요.
2. **선택자 오류**: 웹사이트의 HTML 구조가 변경되면 CSS 선택자를 업데이트해야 합니다.
3. **네트워크 오류**: 타임아웃과 재시도 로직을 구현하세요.
4. **데이터베이스 오류**: Supabase 연결 설정과 테이블 구조를 확인하세요.

### 디버깅 도구

- `scripts/debug_html.py`: HTML 구조 확인
- `scripts/debug_database.py`: 데이터베이스 상태 확인
- `scripts/check_articles_count.py`: 수집된 기사 개수 확인

## 로그 확인

크롤러 실행 로그는 `logs/` 디렉토리에 저장됩니다:

```bash
# 최신 로그 확인
tail -f logs/crawler_$(date +%Y-%m-%d).log

# 특정 크롤러의 로그만 확인
grep "chosun_crawler" logs/crawler_$(date +%Y-%m-%d).log
```
