# 새 언론사 크롤러 추가 가이드

## 개요

이 문서는 opinion.im 프로젝트에 새로운 언론사 크롤러를 추가하는 방법을 설명합니다.

## 프로젝트 구조

```
/opinion.im
  /crawlers
    /major_news        → 주요 언론사 크롤러
    /online_news       → 온라인 매체 크롤러
    /broadcasting      → 방송사 크롤러
  /common             → 공통 모듈
    supabase_manager.py → DB 저장 및 조회
    parser_utils.py     → HTML 파싱, 광고/기자명 제거
    logger.py           → 로깅 유틸
    config.py           → 환경변수 및 상수값 관리
  /scripts            → 실행 스크립트
  /tests              → 테스트 코드
  /docs               → 문서
```

## 새 크롤러 추가 단계

### 1. 크롤러 파일 생성

적절한 디렉토리에 `{언론사명}_politics_crawler.py` 파일을 생성합니다.

**예시: `crawlers/major_news/example_politics_crawler.py`**

```python
#!/usr/bin/env python3
"""
Example 언론사 정치 기사 크롤러
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from common.logger import get_logger
from common.parser_utils import ParserUtils
from common.supabase_manager import SupabaseManager
from common.config import config
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any

class ExamplePoliticsCrawler:
    """Example 언론사 정치 기사 크롤러"""
    
    def __init__(self):
        self.logger = get_logger('example_crawler')
        self.parser = ParserUtils()
        self.db_manager = SupabaseManager()
        
        # 언론사 설정
        self.source_config = config.get_source_config('major_news', 'example')
        self.base_url = self.source_config.get('base_url', 'https://example.com')
        self.politics_url = self.source_config.get('politics_url', 'https://example.com/politics')
        self.table_name = self.source_config.get('table_name', 'example_politics_news')
        
        # HTTP 헤더
        self.headers = {
            'User-Agent': config.USER_AGENT
        }
    
    def get_article_links(self) -> List[str]:
        """기사 목록 페이지에서 기사 링크 수집"""
        try:
            response = requests.get(self.politics_url, headers=self.headers, timeout=config.TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            article_links = []
            
            # 기사 링크 선택자 (언론사별로 다름)
            link_elements = soup.select('a[href*="/article/"]')  # 예시
            
            for link_elem in link_elements[:10]:  # 최대 10개 기사
                href = link_elem.get('href')
                if href:
                    if href.startswith('http'):
                        article_links.append(href)
                    else:
                        article_links.append(self.base_url + href)
            
            self.logger.info(f"기사 링크 {len(article_links)}개 수집")
            return article_links
            
        except Exception as e:
            self.logger.error(f"기사 링크 수집 실패: {str(e)}")
            return []
    
    def parse_article(self, url: str) -> Dict[str, Any]:
        """개별 기사 파싱"""
        try:
            response = requests.get(url, headers=self.headers, timeout=config.TIMEOUT)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 제목 추출 (선택자는 언론사별로 다름)
            title_elem = soup.select_one('h1.title')  # 예시
            title = title_elem.get_text().strip() if title_elem else "제목 없음"
            
            # 본문 추출
            content_elem = soup.select_one('div.article-content')  # 예시
            content = content_elem.get_text().strip() if content_elem else ""
            
            # 날짜 추출
            date_elem = soup.select_one('span.date')  # 예시
            date_str = date_elem.get_text().strip() if date_elem else ""
            parsed_date = self.parser.parse_date(date_str)
            
            # 기자명 추출
            author = self.parser.extract_author(content)
            
            # 제목과 본문 정리
            cleaned_title = self.parser.clean_title(title)
            cleaned_content = self.parser.clean_content(content)
            
            article_data = {
                'title': cleaned_title,
                'content': cleaned_content,
                'link': url,
                'time': parsed_date,
                'author': author,
                'source': self.source_config.get('name', 'Example'),
                'category': '정치'
            }
            
            self.logger.info(f"기사 파싱 성공: {cleaned_title[:50]}...")
            return article_data
            
        except Exception as e:
            self.logger.error(f"기사 파싱 실패: {url} - {str(e)}")
            return {}
    
    def save_articles(self, articles: List[Dict[str, Any]]) -> int:
        """기사들을 데이터베이스에 저장"""
        if not articles:
            return 0
        
        # 테이블 생성 확인
        self.db_manager.create_news_table_if_not_exists(self.table_name)
        
        saved_count = 0
        for article in articles:
            if article and article.get('title'):
                # 중복 확인
                existing = self.db_manager.get_news_by_link(article['link'], self.table_name)
                if not existing:
                    # 새 기사 저장
                    if self.db_manager.insert_news(article, self.table_name):
                        saved_count += 1
                        self.logger.info(f"기사 저장 성공: {article['title'][:50]}...")
                    else:
                        self.logger.warning(f"기사 저장 실패: {article['title'][:50]}...")
                else:
                    self.logger.info(f"기사 이미 존재: {article['title'][:50]}...")
        
        return saved_count
    
    def run(self) -> Dict[str, Any]:
        """크롤러 실행"""
        self.logger.info(f"크롤러 시작: {self.source_config.get('name', 'Example')}")
        
        try:
            # 1. 기사 링크 수집
            article_links = self.get_article_links()
            if not article_links:
                return {'article_count': 0, 'saved_count': 0}
            
            # 2. 기사 파싱
            articles = []
            for link in article_links:
                article = self.parse_article(link)
                if article:
                    articles.append(article)
            
            # 3. 데이터베이스 저장
            saved_count = self.save_articles(articles)
            
            result = {
                'article_count': len(articles),
                'saved_count': saved_count
            }
            
            self.logger.info(f"크롤러 완료: 수집 {len(articles)}개, 저장 {saved_count}개")
            return result
            
        except Exception as e:
            self.logger.error(f"크롤러 실행 중 오류: {str(e)}")
            return {'article_count': 0, 'saved_count': 0}

def main():
    """메인 함수"""
    crawler = ExamplePoliticsCrawler()
    result = crawler.run()
    print(f"수집 결과: {result}")

if __name__ == "__main__":
    main()
```

### 2. 설정 파일 업데이트

`common/config.py`의 `NEWS_SOURCES` 딕셔너리에 새 언론사 정보를 추가합니다.

```python
# common/config.py
NEWS_SOURCES = {
    'major_news': {
        # ... 기존 언론사들 ...
        'example': {
            'name': 'Example 언론사',
            'base_url': 'https://example.com',
            'politics_url': 'https://example.com/politics',
            'table_name': 'example_politics_news'
        }
    }
}
```

### 3. 테스트 코드 작성

`tests/` 디렉토리에 테스트 파일을 생성합니다.

```python
# tests/test_example_crawler.py
import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestExampleCrawler(unittest.TestCase):
    def test_crawler_creation(self):
        """크롤러 생성 테스트"""
        from crawlers.major_news.example_politics_crawler import ExamplePoliticsCrawler
        crawler = ExamplePoliticsCrawler()
        self.assertIsNotNone(crawler)
    
    def test_article_parsing(self):
        """기사 파싱 테스트"""
        # 테스트 코드 작성
        pass

if __name__ == "__main__":
    unittest.main()
```

## 공통 모듈 사용법

### 로거 사용

```python
from common.logger import get_logger

logger = get_logger('crawler_name')
logger.info("정보 메시지")
logger.warning("경고 메시지")
logger.error("오류 메시지")
```

### HTML 파싱 유틸리티

```python
from common.parser_utils import ParserUtils

parser = ParserUtils()

# 날짜 파싱
date = parser.parse_date("2025년 8월 22일")

# 제목 정리
clean_title = parser.clean_title("[속보] 제목")

# 본문 정리 (광고, 기자명 제거)
clean_content = parser.clean_content("본문 내용...")

# HTML에서 텍스트 추출
text = parser.extract_text_from_html("<html>...</html>")

# 기자명 추출
author = parser.extract_author("본문 내용... 김철수 기자...")
```

### 데이터베이스 관리

```python
from common.supabase_manager import SupabaseManager

db_manager = SupabaseManager()

# 테이블 생성
db_manager.create_news_table_if_not_exists('table_name')

# 기사 저장
db_manager.insert_news(article_data, 'table_name')

# 기사 조회
existing = db_manager.get_news_by_link('url', 'table_name')

# 기사 개수 조회
count = db_manager.get_news_count('table_name')
```

## 실행 및 테스트

### 1. 개별 크롤러 실행

```bash
python crawlers/major_news/example_politics_crawler.py
```

### 2. 모든 크롤러 실행

```bash
python scripts/run_all.py
```

### 3. 테스트 실행

```bash
python tests/test_basic.py
python tests/test_example_crawler.py
```

## 주의사항

1. **에러 처리**: 모든 네트워크 요청과 파싱 작업에 적절한 예외 처리를 추가하세요.
2. **로깅**: 중요한 작업과 오류 상황을 로그로 남기세요.
3. **중복 방지**: 이미 수집된 기사는 다시 저장하지 않도록 중복 확인을 구현하세요.
4. **요청 제한**: 서버에 과부하를 주지 않도록 적절한 지연시간을 설정하세요.
5. **선택자 업데이트**: 웹사이트 구조가 변경되면 CSS 선택자를 업데이트해야 할 수 있습니다.

## 문제 해결

### 일반적인 문제들

1. **Import 오류**: `sys.path.append()`를 사용하여 프로젝트 루트를 Python 경로에 추가하세요.
2. **선택자 오류**: 웹사이트의 HTML 구조를 확인하고 올바른 CSS 선택자를 사용하세요.
3. **네트워크 오류**: 타임아웃과 재시도 로직을 구현하세요.
4. **데이터베이스 오류**: Supabase 연결 설정과 테이블 구조를 확인하세요.

### 디버깅 팁

1. `debug_html.py` 스크립트를 사용하여 HTML 구조를 확인하세요.
2. 로그 파일을 확인하여 오류 원인을 파악하세요.
3. 작은 데이터셋으로 먼저 테스트하세요.
4. 웹사이트의 robots.txt를 확인하여 크롤링 정책을 준수하세요.
