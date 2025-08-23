from typing import List, Dict
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
프레시안 정치 기사 크롤러 (최적화 버전)
프레시안 웹사이트에서 정치 기사를 수집하여 Supabase DB에 저장합니다.
"""

import asyncio
import aiohttp
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich import box
import re
from utils.supabase_manager_unified import UnifiedSupabaseManager
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.common.html_parser import HTMLParserUtils

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rich 콘솔 설정
console = Console()

class PressianPoliticsCrawler:
    def __init__(self):
        self.base_url = "https://www.pressian.com"
        self.politics_url = "https://www.pressian.com/pages/news-politics-list"
        self.supabase_manager = UnifiedSupabaseManager()
        self.media_outlet = "프레시안"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    async def get_page_content(self, session, url):
        """페이지 내용을 가져옵니다."""
        try:
            async with session.get(url, headers=self.headers) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    logger.warning(f"HTTP {response.status}: {url}")
                    return None
        except Exception as e:
            logger.error(f"페이지 로드 실패 ({url}): {e}")
            return None

    async def collect_article_links(self, session, max_articles=100):
        """기사 링크들을 수집합니다."""
        console.print("🔍 프레시안 정치 기사 링크 수집 중...")
        
        all_links = []
        page = 1
        
        while len(all_links) < max_articles and page <= 10:  # 최대 10페이지
            if page == 1:
                url = self.politics_url
            else:
                url = f"{self.politics_url}?page={page}"
            
            console.print(f"📄 {page}페이지 수집 중... ({url})")
            
            html_content = await self.get_page_content(session, url)
            if not html_content:
                break
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 기사 링크 찾기: div.arl_022 ul.list li p.title a
            article_elements = soup.select('div.arl_022 ul.list li')
            
            page_links = []
            for element in article_elements:
                link_elem = element.select_one('p.title a')
                if link_elem and link_elem.get('href'):
                    href = link_elem.get('href')
                    if href.startswith('/pages/articles/'):
                        full_url = f"{self.base_url}{href}"
                        page_links.append(full_url)
            
            if not page_links:
                console.print(f"❌ {page}페이지에서 기사를 찾을 수 없습니다.")
                break
            
            all_links.extend(page_links)
            console.print(f"✅ {page}페이지에서 {len(page_links)}개 기사 링크 수집 (총 {len(all_links)}개)")
            
            page += 1
        
        # 목표 개수만큼 자르기
        if len(all_links) > max_articles:
            all_links = all_links[:max_articles]
        
        console.print(f"🎯 총 {len(all_links)}개 기사 링크 수집 완료")
        return all_links

    def extract_article_content(self, html_content, url):
        """기사 제목과 본문을 추출합니다."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출 - 프레시안의 경우 title 태그나 og:title 메타태그에서 추출
        title = None
        
        # 1. og:title 메타태그에서 제목 추출 (가장 정확)
        meta_title = soup.find('meta', property='og:title')
        if meta_title and meta_title.get('content'):
            title = meta_title.get('content').strip()
        
        # 2. title 태그에서 제목 추출
        if not title:
            page_title = soup.find('title')
            if page_title:
                title = page_title.get_text(strip=True)
                # 사이트명 제거 (예: " - 프레시안")
                if ' - ' in title:
                    title = title.split(' - ')[0].strip()
        
        # 3. 다른 선택자들 (후원 메시지가 아닌 경우만)
        if not title or '후원' in title:
            title_selectors = [
                'h1',
                '.article_title',
                'h1.title',
                'h3.title',
                'p.title',
                '.title'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    candidate_title = title_elem.get_text(strip=True)
                    if candidate_title and len(candidate_title) > 10 and '후원' not in candidate_title:
                        title = candidate_title
                        break
        
        if not title or '후원' in title:
            title = f"프레시안 기사 - {url.split('/')[-1]}"

        # 본문 추출
        content = None
        content_selectors = [
            'div.article_body',
            'div.article-content',
            'div.content',
            'div.body',
            'div.article-body',
            'div.text',
            'article',
            'div.arl_022'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # 불필요한 요소 제거
                for unwanted in content_elem.select('script, style, .ad, .advertisement, .related, .comment, .ui-control, .font-control, .share-control, .sidebar, .side-news, .related-news, .reading-mode, .dark-mode, .font-size, .bookmark, .print, .share, .reaction, .recommend, .like, .subscribe, .donation, .footer, .navigation, .menu, .header, .banner'):
                    unwanted.decompose()
                
                content = content_elem.get_text(strip=True, separator='\n')
                if content and len(content) > 100:
                    # 불필요한 텍스트 패턴 제거
                    unwanted_patterns = [
                        '읽기모드', '다크모드', '폰트크기', '가가가가가가', '북마크', '공유하기', '프린트',
                        '기사반응', '추천해요', '좋아요', '감동이에요', '화나요', '슬퍼요',
                        'My 추천 기사', '가장 많이 읽은 기사', '댓글 많은 기사', '실시간 최신 뉴스',
                        '주요뉴스', '이슈NOW', '관련기사', '더보기', '목록', '이전글', '다음글',
                        '구독', '기사 후원하기', '카카오톡', '페이스북', '트위터', '라인', '링크복사',
                        '참사는 수습했지만', '尹 대통령 파면', '3대 특검', '이재명 정부',
                        '미국 가는', '정의선', '석유화학', '정부, 연내', '꽃이 된'
                    ]
                    
                    for pattern in unwanted_patterns:
                        content = content.replace(pattern, '')
                    
                    # 기자 정보 이후의 모든 불필요한 내용 제거
                    lines = content.split('\n')
                    cleaned_lines = []
                    for line in lines:
                        # 기자 정보를 찾으면 그 이후는 모두 제거
                        if '기자' in line and len(line.strip()) < 30:
                            cleaned_lines.append(line.strip())
                            break
                        cleaned_lines.append(line)
                    
                    content = '\n'.join(cleaned_lines)
                    
                    # 정규식 패턴으로 추가 정리
                    import re
                    
                    # 이메일 주소 제거
                    content = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', content)
                    
                    # 해시태그 제거
                    content = re.sub(r'#\s*\w+', '', content)
                    
                    # 숫자만 있는 라인 제거
                    content = re.sub(r'^\d+$', '', content, flags=re.MULTILINE)
                    
                    # 시간 형식 제거 (12:10 같은)
                    content = re.sub(r'^\d{1,2}:\d{2}$', '', content, flags=re.MULTILINE)
                    
                    # 연속된 빈 줄 정리
                    content = '\n'.join([line.strip() for line in content.split('\n') if line.strip()])
                    
                    if content and len(content) > 100:
                        break
        
        return title, content

    def extract_publish_date(self, html_content):
        """발행일을 추출합니다."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 날짜 선택자들
        date_selectors = [
            '.date',
            'p.date',
            '.publish-date',
            '.article-date',
            'time',
            '[datetime]'
        ]
        
        for selector in date_selectors:
            date_elem = soup.select_one(selector)
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                if date_text:
                    # "기사입력" 문자열 제거
                    date_text = date_text.replace('기사입력', '').strip()
                    
                    # 프레시안 날짜 형식: "2025.08.21. 09:59:25"
                    try:
                        # 날짜 파싱
                        date_match = re.search(r'(\d{4})\.(\d{2})\.(\d{2})\.\s+(\d{2}):(\d{2}):(\d{2})', date_text)
                        if date_match:
                            year, month, day, hour, minute, second = date_match.groups()
                            date_obj = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second))
                            return date_obj.isoformat()
                    except Exception as e:
                        logger.error(f"날짜 파싱 실패: {date_text} - {e}")
                        continue
        
        # 날짜를 찾을 수 없으면 현재 시간 사용
        return datetime.now().isoformat()

    async def process_single_article(self, session, url, semaphore):
        """단일 기사를 처리합니다."""
        async with semaphore:
            try:
                # 기사가 이미 DB에 있는지 확인
                existing_article = self.supabase_manager.client.table('articles').select('id').eq('url', url).execute()
                if existing_article.data:
                    return True  # 이미 존재하는 기사
                
                # 기사 페이지 내용 가져오기
                html_content = await self.get_page_content(session, url)
                if not html_content:
                    return False
                
                # 제목과 본문 추출
                title, content = self.extract_article_content(html_content, url)
                if not title or not content:
                    return False
                
                # 발행일 추출
                publish_date = self.extract_publish_date(html_content)
                
                # 새 기사 삽입
                article_data = {
                    'title': title,
                    'url': url,
                    'content': content,
                    'published_at': publish_date,
                    'media_id': self.supabase_manager.get_media_outlet(self.media_outlet)['id'],
                    'issue_id': 6  # 임시 issue_id
                }
                
                result = self.supabase_manager.insert_article(article_data)
                return result is not None
                
            except Exception as e:
                logger.error(f"기사 처리 실패 ({url}): {e}")
                return False

    async def crawl_articles(self, article_links):
        """기사들을 동시에 크롤링합니다."""
        console.print(f"\n📰 {len(article_links)}개 기사 크롤링 시작...")
        
        # 세션 설정 - 성능 최적화
        connector = aiohttp.TCPConnector(limit=200, limit_per_host=50)
        timeout = aiohttp.ClientTimeout(total=10, connect=3)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                
                task = progress.add_task("기사 정보 수집 중...", total=len(article_links))
                
                # 동시 처리를 위한 세마포어 (최대 30개 동시 요청)
                semaphore = asyncio.Semaphore(30)
                
                async def process_with_progress(url):
                    result = await self.process_single_article(session, url, semaphore)
                    progress.update(task, advance=1)
                    return result
                
                # 모든 기사를 동시에 처리
                results = await asyncio.gather(*[process_with_progress(url) for url in article_links], return_exceptions=True)
                
                success_count = sum(1 for result in results if result is True)
                failed_count = len(results) - success_count
        
        return success_count, failed_count

    async def run(self):
        """크롤러를 실행합니다."""
        start_time = datetime.now()
        
        console.print("🚀 프레시안 정치 기사 크롤러 시작!")
        console.print(f"📅 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 세션 설정
        connector = aiohttp.TCPConnector(limit=200, limit_per_host=50)
        timeout = aiohttp.ClientTimeout(total=10, connect=3)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # 1. 기사 링크 수집
            article_links = await self.collect_article_links(session)
            
            if not article_links:
                console.print("❌ 수집할 기사가 없습니다.")
                return
            
            # 2. 기사 크롤링
            success_count, failed_count = await self.crawl_articles(article_links)
        
        # 결과 요약
        end_time = datetime.now()
        duration = end_time - start_time
        
        # 결과 테이블 생성
        table = Table(title="프레시안 크롤링 결과", box=box.ROUNDED)
        table.add_column("항목", style="cyan", no_wrap=True)
        table.add_column("값", style="magenta")
        
        table.add_row("총 기사 수", str(len(article_links)))
        table.add_row("성공", f"{success_count}개", style="green")
        table.add_row("실패", f"{failed_count}개", style="red")
        table.add_row("성공률", f"{(success_count/len(article_links)*100):.1f}%")
        table.add_row("소요 시간", f"{duration.total_seconds():.2f}초")
        table.add_row("평균 속도", f"{len(article_links)/duration.total_seconds():.2f} 기사/초")
        
        console.print(table)
        console.print(f"✅ 프레시안 크롤링 완료! 🎉")


    async def collect_all_articles(self) -> List[Dict]:
        """모든 기사 수집 (표준 인터페이스)"""
        try:
            result = await self.crawl_articles()
            if hasattr(self, 'articles') and self.articles:
                return self.articles
            elif result:
                return result if isinstance(result, list) else []
            else:
                return []
        except Exception as e:
            print(f"❌ 기사 수집 실패: {str(e)}")
            return getattr(self, 'articles', [])


    async def save_to_supabase(self, articles: List[Dict]) -> Dict[str, int]:
        """Supabase에 기사 저장"""
        if not articles:
            return {"success": 0, "failed": 0}
        
        success_count = 0
        failed_count = 0
        
        try:
            for article in articles:
                if hasattr(self, 'supabase_manager') and self.supabase_manager:
                    if self.supabase_manager.insert_article(article):
                        success_count += 1
                    else:
                        failed_count += 1
                else:
                    failed_count += 1
        except Exception as e:
            print(f"❌ Supabase 저장 오류: {str(e)}")
            failed_count = len(articles)
        
        return {"success": success_count, "failed": failed_count}

async def main():
    """메인 함수"""
    crawler = PressianPoliticsCrawler()
    await crawler.run()

if __name__ == "__main__":
    asyncio.run(asyncio.run(main()))