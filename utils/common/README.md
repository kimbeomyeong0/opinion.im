# 공통 유틸리티 모듈

크롤러들이 공통으로 사용할 수 있는 유틸리티 모듈들입니다.

## 📁 모듈 목록

### 1. `http_client.py` - HTTP 클라이언트 통합 관리
- **httpx**와 **aiohttp** 두 라이브러리를 통합 관리
- 크롤러별로 선호하는 HTTP 클라이언트 선택 가능
- 배치 요청 및 동시성 제어 지원

### 2. `html_parser.py` - HTML 파싱 공통 기능
- 다양한 날짜 형식 파싱 (한국어, 점, 하이픈, 슬래시 등)
- 제목 정리 및 본문 추출
- 광고/스크립트 태그 제거
- 링크 패턴 매칭

## 🚀 사용법

### HTTP 클라이언트 사용

```python
from utils.common.http_client import HTTPClientManager, make_request

# 방법 1: 컨텍스트 매니저 사용 (권장)
async with HTTPClientManager("httpx", timeout=10.0) as client:
    html = await client.get("https://example.com")
    result = await client.post("https://api.example.com", data={"key": "value"})

# 방법 2: 편의 함수 사용
html = await make_request("https://example.com", "httpx", "GET")
result = await make_request("https://api.example.com", "aiohttp", "POST", data={"key": "value"})

# 방법 3: 배치 요청
urls = ["https://example1.com", "https://example2.com", "https://example3.com"]
results = await make_requests_batch(urls, "httpx", "GET", max_concurrent=5)
```

### HTML 파싱 사용

```python
from utils.common.html_parser import HTMLParserUtils, parse_date_simple, clean_title_simple

# 날짜 파싱
date = HTMLParserUtils.parse_date("2025.08.22")  # "2025-08-22"
date = HTMLParserUtils.parse_date("25.08.22")    # "2025-08-22"
date = HTMLParserUtils.parse_date("8월 22일")    # "2025-08-22"

# 제목 정리
clean_title = HTMLParserUtils.clean_title("<strong>제목</strong>")  # "제목"

# 본문 추출
content = HTMLParserUtils.extract_article_content(
    html,
    content_selectors=['div.content', 'div.article_body'],
    title_selectors=['h1.title', 'h2.article_title'],
    date_selectors=['span.date', 'div.publish_date']
)

# 편의 함수들
date = parse_date_simple("2025.08.22")
title = clean_title_simple("<strong>제목</strong>")
```

## 🔧 크롤러별 적용 예시

### YTN 크롤러 (httpx 사용)
```python
from utils.common.http_client import make_request
from utils.common.html_parser import HTMLParserUtils

class YTNPoliticsCrawler:
    async def _make_request(self, url: str):
        return await make_request(url, "httpx", "GET", timeout=10.0)
    
    def _parse_date(self, date_str: str):
        return HTMLParserUtils.parse_date(date_str)
    
    def _clean_title(self, title: str):
        return HTMLParserUtils.clean_title(title)
```

### 조선일보 크롤러 (aiohttp 사용)
```python
from utils.common.http_client import HTTPClientManager
from utils.common.html_parser import HTMLParserUtils

class ChosunPoliticsCrawler:
    async def __aenter__(self):
        self.http_client = HTTPClientManager("aiohttp", timeout=5.0)
        return await self.http_client.__aenter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def get_article(self, url: str):
        return await self.http_client.get(url)
```

## 📊 지원하는 날짜 형식

| 형식 | 예시 | 결과 |
|------|------|------|
| 한국어 | 2025년 8월 22일 | 2025-08-22 |
| 점 구분 | 2025.08.22 | 2025-08-22 |
| 점 구분 (2자리 년도) | 25.08.22 | 2025-08-22 |
| 하이픈 | 2025-08-22 | 2025-08-22 |
| 슬래시 | 2025/08/22 | 2025-08-22 |
| 공백 | 2025 08 22 | 2025-08-22 |

## ⚠️ 주의사항

1. **HTTP 클라이언트 선택**: 크롤러의 특성에 맞게 선택
   - `httpx`: 간단한 요청, 빠른 응답
   - `aiohttp`: 복잡한 세션 관리, 높은 동시성

2. **날짜 파싱**: 2자리 년도는 20xx년으로 가정
   - 25.08.22 → 2025-08-22
   - 99.08.22 → 2099-08-22

3. **에러 처리**: 모든 함수는 실패 시 None 반환
   - 적절한 에러 처리 로직 필요

## 🔄 마이그레이션 가이드

기존 크롤러를 공통 유틸리티로 변경하려면:

1. **Import 변경**:
   ```python
   # 이전
   import httpx
   import aiohttp
   
   # 새로운 방식
   from utils.common.http_client import make_request, HTTPClientManager
   ```

2. **HTTP 요청 변경**:
   ```python
   # 이전
   async with httpx.AsyncClient() as client:
       response = await client.get(url)
   
   # 새로운 방식
   html = await make_request(url, "httpx", "GET")
   ```

3. **HTML 파싱 변경**:
   ```python
   # 이전
   def _parse_date(self, date_str):
       # 복잡한 파싱 로직
   
   # 새로운 방식
   from utils.common.html_parser import parse_date_simple
   date = parse_date_simple(date_str)
   ```
