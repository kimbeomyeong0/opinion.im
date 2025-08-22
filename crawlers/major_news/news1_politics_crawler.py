#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
뉴스1 정치 기사 크롤러
- Ajax API를 활용하여 빠른 기사 수집
- 20초 내에 100개 기사 수집 목표
- 본문을 깔끔하게 추출 (군더더기 제거)
- bias는 media_outlets.bias를 자동으로 사용
"""

import asyncio
import aiohttp
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from rich import box
import re
import json
import sys
import os
from playwright.async_api import async_playwright
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'utils'))
from legacy.supabase_manager_v2 import SupabaseManagerV2

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rich 콘솔 설정
console = Console()

class News1PoliticsCrawler:
    def __init__(self):
        self.base_url = "https://www.news1.kr"
        self.politics_url = "https://www.news1.kr/politics"
        self.supabase_manager = SupabaseManagerV2()
        self.media_outlet = "뉴스1"
        self.media_bias = "left"  # 뉴스1은 좌편향 성향
        
        # media_outlets에서 뉴스1 정보 가져오기
        self.media_id = None
        self._init_media_outlet()
        
        # 크롤링 설정
        self.max_articles = 100
        self.max_workers = 20
        self.timeout = 10
        self.delay = 0.05
        
    def _init_media_outlet(self):
        """media_outlets에서 뉴스1 정보를 초기화합니다."""
        try:
            media_outlet = self.supabase_manager.get_media_outlet(self.media_outlet)
            if media_outlet:
                self.media_id = media_outlet['id']
                console.print(f"✅ 뉴스1 media_id: {self.media_id}, bias: {self.media_bias}")
            else:
                # 뉴스1이 없으면 생성
                self.media_id = self.supabase_manager.create_media_outlet(self.media_outlet, self.media_bias)
                console.print(f"✅ 뉴스1 생성됨 - media_id: {self.media_id}, bias: {self.media_bias}")
        except Exception as e:
            console.print(f"[red]뉴스1 media_outlet 초기화 실패: {str(e)}[/red]")
            self.media_id = 20  # 기본값 사용
    
        # Ajax API 설정
        self.api_url = "https://www.news1.kr/api/article/list"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Referer': 'https://www.news1.kr/politics',
            'X-Requested-With': 'XMLHttpRequest'
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

    async def collect_article_links_via_api(self, session) -> list:
        """Ajax API를 통해 기사 링크들을 수집합니다."""
        console.print("🔍 뉴스1 Ajax API로 정치 기사 링크 수집 중...")
        
        all_links = []
        start_page = 1
        max_pages = 10  # 100개 기사 = 10페이지 × 10개씩
        
        try:
            # 올바른 뉴스1 API 엔드포인트
            api_url = "https://rest.news1.kr/v6/section/politics/latest"
            
            for page in range(start_page, start_page + max_pages):
                params = {
                    'start': page,
                    'limit': 10
                }
                
                console.print(f"📄 API 페이지 {page} 요청 중... (start={page}, limit=10)")
                
                async with session.get(api_url, params=params, headers=self.headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if isinstance(data, list) and len(data) > 0:
                            page_links = []
                            for article in data:
                                if 'url' in article and '/politics/' in article['url']:
                                    if article['url'].startswith('/'):
                                        full_url = f"{self.base_url}{article['url']}"
                                    else:
                                        full_url = article['url']
                                    page_links.append(full_url)
                            
                            # 새로 발견된 링크만 추가
                            new_links = [link for link in page_links if link not in all_links]
                            all_links.extend(new_links)
                            
                            console.print(f"📄 API 페이지 {page}: {len(new_links)}개 새 기사 발견 (총 {len(all_links)}개)")
                            
                            # 더 이상 새 기사가 없으면 중단
                            if len(new_links) == 0:
                                console.print(f"📄 API 페이지 {page}: 더 이상 새 기사 없음, 수집 완료")
                                break
                            
                            # API 호출 간 딜레이
                            await asyncio.sleep(0.2)
                        else:
                            console.print(f"📄 API 페이지 {page}: 데이터 형식 오류")
                            break
                    else:
                        console.print(f"❌ API 페이지 {page} 호출 실패: {response.status}")
                        break
            
            console.print(f"✅ API로 총 {len(all_links)}개 기사 링크 수집 완료")
            return all_links
                    
        except Exception as e:
            console.print(f"❌ API 호출 중 오류 발생: {str(e)}")
            return all_links

    async def collect_article_links_fallback(self, session) -> list:
        """HTML 파싱으로 기사 링크들을 수집합니다 (100개 달성까지)"""
        console.print("🔍 HTML 파싱으로 뉴스1 정치 기사 링크 수집 중...")
        
        all_links = []
        target_count = 100
        
        # 1단계: 메인 정치 페이지에서 3개 섹션 모두 파싱
        try:
            links = await self._collect_all_sections(session, self.politics_url)
            all_links.extend(links)
            # 중복 제거
            all_links = list(set(all_links))
            console.print(f"📄 1단계 완료: {len(all_links)}개 기사 수집")
        except Exception as e:
            console.print(f"[red]1단계 실패: {str(e)}[/red]")
        
        # 2단계: 100개 미달시 하위 카테고리에서 추가 수집
        if len(all_links) < target_count:
            shortage = target_count - len(all_links)
            console.print(f"🔍 2단계: {shortage}개 부족, 하위 카테고리에서 추가 수집...")
            
            sub_categories = [
                '/politics/president',
                '/politics/assembly', 
                '/politics/pm-bai-comm',
                '/politics/general-politics'
            ]
            
            for category in sub_categories:
                if len(all_links) >= target_count:
                    break
                    
                try:
                    category_url = f"{self.base_url}{category}"
                    additional_links = await self._collect_with_playwright_enhanced(category_url, target_count - len(all_links))
                    
                    # 중복 체크 후 추가
                    new_links = [link for link in additional_links if link not in all_links]
                    all_links.extend(new_links)
                    
                    console.print(f"📄 {category}: {len(new_links)}개 새 기사 추가 (총 {len(all_links)}개)")
                    
                except Exception as e:
                    console.print(f"[red]{category} 수집 실패: {str(e)}[/red]")
        
        # 최종 중복 제거
        all_links = list(set(all_links))
        
        if len(all_links) >= target_count:
            console.print(f"✅ 목표 달성! 총 {len(all_links)}개 기사 링크 수집 완료")
        else:
            console.print(f"⚠️  목표 미달: {len(all_links)}개 기사 수집 ({target_count - len(all_links)}개 부족)")
        
        return all_links
    
    async def _collect_all_sections(self, session, url: str) -> list:
        """3개 섹션을 모두 파싱하여 기사를 수집합니다."""
        all_links = []
        
        try:
            # 기본 HTML 파싱으로 3개 섹션 모두 수집
            html_content = await self.get_page_content(session, url)
            if html_content:
                soup = BeautifulSoup(html_content, 'html.parser')
                links = self._extract_all_sections_from_html(soup)
                all_links.extend(links)
                console.print(f"📄 기본 HTML 파싱: {len(links)}개 기사 발견")
            
            # Playwright로 더보기 버튼 클릭하여 추가 기사 수집
            playwright_links = await self._collect_with_playwright(url)
            all_links.extend(playwright_links)
            console.print(f"📄 Playwright 더보기: {len(playwright_links)}개 추가 기사 발견")
            
        except Exception as e:
            console.print(f"[red]섹션별 파싱 실패: {str(e)}[/red]")
        
        return all_links
    
    async def _collect_with_playwright(self, url: str) -> list:
        """Playwright를 사용하여 더보기 버튼을 클릭하고 추가 기사를 수집합니다."""
        all_links = []
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # 페이지 로드
                await page.goto(url, wait_until='networkidle')
                await asyncio.sleep(2)
                
                # 초기 기사 수 확인
                initial_count = len(await page.query_selector_all('h2.n1-header-title-1-2 a'))
                console.print(f"📄 초기 기사 수: {initial_count}개")
                
                # 더보기 버튼 클릭 반복 (최대 15회로 증가)
                click_count = 0
                max_clicks = 15
                
                while click_count < max_clicks:
                    try:
                        # 더보기 버튼 찾기
                        more_button = await page.query_selector('button.read-more, .read-more, [class*="more"]')
                        if not more_button:
                            console.print(f"📄 더보기 버튼 없음, 수집 완료")
                            break
                        
                        # 더보기 버튼 클릭
                        await more_button.click()
                        await asyncio.sleep(2)  # 로딩 대기
                        
                        # 새로운 기사 수 확인
                        new_count = len(await page.query_selector_all('h2.n1-header-title-1-2 a'))
                        new_articles = new_count - initial_count
                        
                        if new_articles > 0:
                            console.print(f"📄 더보기 클릭 {click_count + 1}: {new_articles}개 새 기사 발견 (총 {new_count}개)")
                            initial_count = new_count
                        else:
                            console.print(f"📄 더보기 클릭 {click_count + 1}: 새 기사 없음")
                        
                        click_count += 1
                        
                        # 150개 달성 시 중단 (여유분 확보)
                        if new_count >= 150:
                            console.print(f"📄 150개 기사 달성! 수집 완료")
                            break
                            
                    except Exception as e:
                        console.print(f"[red]더보기 클릭 {click_count + 1} 실패: {str(e)}[/red]")
                        break
                
                # 최종 HTML에서 모든 기사 링크 추출
                final_html = await page.content()
                soup = BeautifulSoup(final_html, 'html.parser')
                final_links = self._extract_all_sections_from_html(soup)
                
                await browser.close()
                return final_links
                
        except Exception as e:
            console.print(f"[red]Playwright 실행 실패: {str(e)}[/red]")
            return []
    
    async def _collect_with_playwright_enhanced(self, url: str, needed_count: int) -> list:
        """향상된 Playwright로 필요한 만큼만 추가 기사를 수집합니다."""
        all_links = []
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # 페이지 로드
                await page.goto(url, wait_until='networkidle')
                await asyncio.sleep(2)
                
                # 초기 기사 수 확인
                initial_count = len(await page.query_selector_all('h2.n1-header-title-1-2 a'))
                console.print(f"📄 {url} 초기 기사: {initial_count}개")
                
                # 더보기 버튼 클릭 반복 (필요한 만큼)
                click_count = 0
                max_clicks = 10
                target_count = initial_count + needed_count + 20  # 여유분 추가
                
                while click_count < max_clicks:
                    try:
                        # 더보기 버튼 찾기
                        more_button = await page.query_selector('button.read-more, .read-more, [class*="more"]')
                        if not more_button:
                            break
                        
                        # 더보기 버튼 클릭
                        await more_button.click()
                        await asyncio.sleep(1.5)  # 로딩 대기
                        
                        # 새로운 기사 수 확인
                        new_count = len(await page.query_selector_all('h2.n1-header-title-1-2 a'))
                        
                        if new_count > initial_count:
                            console.print(f"📄 더보기 클릭 {click_count + 1}: {new_count}개 기사 (목표: {target_count}개)")
                            initial_count = new_count
                        
                        click_count += 1
                        
                        # 목표 달성 시 중단
                        if new_count >= target_count:
                            break
                            
                    except Exception as e:
                        console.print(f"[red]더보기 클릭 실패: {str(e)}[/red]")
                        break
                
                # 최종 HTML에서 기사 링크 추출
                final_html = await page.content()
                soup = BeautifulSoup(final_html, 'html.parser')
                final_links = self._extract_all_sections_from_html(soup)
                
                await browser.close()
                return final_links
                
        except Exception as e:
            console.print(f"[red]향상된 Playwright 실행 실패: {str(e)}[/red]")
            return []
    
    async def _collect_with_more_button(self, session, url: str, page_name: str) -> list:
        """더보기 버튼을 클릭하여 더 많은 기사를 수집합니다."""
        all_links = []
        current_url = url
        page_count = 1
        
        while True:
            try:
                html_content = await self.get_page_content(session, current_url)
                if not html_content:
                    break
                
                soup = BeautifulSoup(html_content, 'html.parser')
                links = self._extract_article_links_from_html(soup)
                
                # 새로 발견된 링크만 추가
                new_links = [link for link in links if link not in all_links]
                all_links.extend(new_links)
                
                console.print(f"📄 {page_name} (페이지 {page_count}): {len(new_links)}개 새 기사 발견 (총 {len(all_links)}개)")
                
                # 더보기 버튼이 있는지 확인
                more_button = soup.select_one('button.read-more')
                if not more_button:
                    console.print(f"📄 {page_name}: 더보기 버튼 없음, 수집 완료")
                    break
                
                # 더보기 버튼 클릭 시뮬레이션 (URL 파라미터 추가)
                page_count += 1
                if '?' in current_url:
                    current_url = f"{url}&page={page_count}"
                else:
                    current_url = f"{url}?page={page_count}"
                
                # 최대 10페이지까지만 수집 (무한 루프 방지)
                if page_count > 10:
                    console.print(f"📄 {page_name}: 최대 페이지 수(10) 도달, 수집 완료")
                    break
                
                # 페이지 간 딜레이
                await asyncio.sleep(0.5)
                
            except Exception as e:
                console.print(f"[red]{page_name} 페이지 {page_count} 파싱 실패: {str(e)}[/red]")
                break
        
        return all_links
    
    def _extract_all_sections_from_html(self, soup) -> list:
        """3개 섹션을 모두 파싱하여 기사 링크를 추출합니다."""
        links = []
        
        # 1. 최상단 (메인 기사) - h2.n1-header-subtop-2 a
        main_articles = soup.select('h2.n1-header-subtop-2 a')
        for article in main_articles:
            href = article.get('href')
            if href and '/politics/' in href:
                if href.startswith('/'):
                    full_url = f"{self.base_url}{href}"
                else:
                    full_url = href
                if full_url not in links:
                    links.append(full_url)
        
        # 2. 중간 (주요기사) - h2.text-limit-2-row.n1-header-title-7 a
        featured_articles = soup.select('h2.text-limit-2-row.n1-header-title-7 a')
        for article in featured_articles:
            href = article.get('href')
            if href and '/politics/' in href:
                if href.startswith('/'):
                    full_url = f"{self.base_url}{href}"
                else:
                    full_url = href
                if full_url not in links:
                    links.append(full_url)
        
        # 3. 하단 (최신기사) - h2.n1-header-title-1-2.text-limit-2-row a
        latest_articles = soup.select('h2.n1-header-title-1-2.text-limit-2-row a')
        for article in latest_articles:
            href = article.get('href')
            if href and '/politics/' in href:
                if href.startswith('/'):
                    full_url = f"{self.base_url}{href}"
                else:
                    full_url = href
                if full_url not in links:
                    links.append(full_url)
        
        # 4. 추가 기사들 (더보기 클릭 후 로드된 기사들)
        additional_articles = soup.select('h2.n1-header-title-1-2 a')
        for article in additional_articles:
            href = article.get('href')
            if href and '/politics/' in href:
                if href.startswith('/'):
                    full_url = f"{self.base_url}{href}"
                else:
                    full_url = href
                if full_url not in links:
                    links.append(full_url)
        
        console.print(f"📄 섹션별 파싱 결과:")
        console.print(f"   - 최상단 (메인): {len(main_articles)}개")
        console.print(f"   - 중간 (주요): {len(featured_articles)}개")
        console.print(f"   - 하단 (최신): {len(latest_articles)}개")
        console.print(f"   - 추가 기사: {len(additional_articles)}개")
        console.print(f"   - 총 중복 제거 후: {len(links)}개")
        
        return links
    
    def _extract_article_links_from_html(self, soup) -> list:
        """HTML에서 기사 링크를 추출합니다."""
        links = []
        article_elements = soup.find_all('a', href=True)
        
        for element in article_elements:
            href = element.get('href')
            # 실제 기사 URL만 필터링 (카테고리 페이지 제외)
            if (href and '/politics/' in href and 
                any(keyword in href for keyword in ['/president/', '/assembly/', '/pm-bai-comm/', '/general-politics/']) and
                not href.endswith(('/president', '/assembly', '/pm-bai-comm', '/general-politics'))):
                
                if href.startswith('/'):
                    full_url = f"{self.base_url}{href}"
                else:
                    full_url = href
                
                if full_url not in links:
                    links.append(full_url)
        
        return links

    def extract_article_content(self, html_content: str, url: str) -> tuple:
        """기사 내용을 추출합니다."""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 뉴스1은 기사 내용이 JSON에 있음 - __NEXT_DATA__ 스크립트에서 추출
            next_data_script = soup.find('script', {'id': '__NEXT_DATA__'})
            if next_data_script:
                try:
                    import json
                    data = json.loads(next_data_script.string)
                    
                    # JSON에서 기사 데이터 추출
                    article_view = data.get('props', {}).get('pageProps', {}).get('articleView', {})
                    
                    # 제목 추출
                    title = article_view.get('title', '')
                    
                    # 본문 추출 - contentArrange에서 type이 "text"인 것들
                    content_parts = []
                    content_arrange = article_view.get('contentArrange', [])
                    for item in content_arrange:
                        if item.get('type') == 'text':
                            text_content = item.get('content', '').strip()
                            if text_content and len(text_content) > 10:
                                # 기자 이메일 제외
                                if '@news1.kr' not in text_content:
                                    content_parts.append(text_content)
                    
                    content = '\n\n'.join(content_parts)
                    
                    # 발행일 추출
                    publish_date = None
                    pubdate_at = article_view.get('pubdate_at', '')
                    if pubdate_at:
                        publish_date = self.parse_date(pubdate_at)
                    
                    # 제목과 본문이 모두 있어야 유효한 기사
                    if title and content and len(content) > 50:
                        return title, content, publish_date
                
                except json.JSONDecodeError as e:
                    console.print(f"[yellow]JSON 파싱 실패, HTML 파싱으로 대체: {str(e)}[/yellow]")
            
            # JSON 파싱 실패 시 기존 HTML 파싱 방식 사용
            # 제목 추출: h1.article-h2-header-title
            title = ""
            title_elem = soup.select_one('h1.article-h2-header-title')
            if title_elem:
                title = title_elem.get_text(strip=True)
            
            # 본문 추출: div#articleBodyContent p
            content = ""
            content_elem = soup.select_one('div#articleBodyContent')
            if content_elem:
                # 불필요한 요소 제거
                for unwanted in content_elem.select('.ads-article-warp, figure, .article_content_stitle'):
                    unwanted.decompose()
                
                # 본문 텍스트 추출
                paragraphs = content_elem.find_all('p')
                content_parts = []
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if text and len(text) > 10:
                        content_parts.append(text)
                
                content = '\n\n'.join(content_parts)
            
            # 발행일 추출: #article_created time
            publish_date = None
            date_elem = soup.select_one('#article_created time')
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                publish_date = self.parse_date(date_text)
            
            # HTML 파싱도 실패한 경우
            if not title or not content or len(content) < 50:
                return None, None, None
                
            return title, content, publish_date
            
        except Exception as e:
            logger.error(f"기사 내용 추출 실패 ({url}): {e}")
            return None, None, None

    def parse_date(self, date_text: str) -> str:
        """날짜 텍스트를 파싱합니다."""
        try:
            # 뉴스1 날짜 형식: "2024.01.15 14:30" 또는 "1시간 전" 등
            if '시간 전' in date_text:
                hours = int(re.search(r'(\d+)시간', date_text).group(1))
                now = datetime.now()
                date_obj = now.replace(hour=now.hour - hours, minute=0, second=0, microsecond=0)
                return date_obj.isoformat()
            elif '분 전' in date_text:
                minutes = int(re.search(r'(\d+)분', date_text).group(1))
                now = datetime.now()
                date_obj = now.replace(minute=now.minute - minutes, second=0, microsecond=0)
                return date_obj.isoformat()
            elif re.match(r'\d{4}\.\d{2}\.\d{2}', date_text):
                # "2024.01.15" 형식
                date_obj = datetime.strptime(date_text.split()[0], '%Y.%m.%d')
                return date_obj.isoformat()
            else:
                # 현재 시간 사용
                return datetime.now().isoformat()
        except Exception as e:
            logger.error(f"날짜 파싱 실패: {date_text} - {e}")
            return datetime.now().isoformat()

    async def process_single_article(self, session, url, semaphore):
        """단일 기사를 처리합니다."""
        async with semaphore:
            try:
                # 기사가 이미 DB에 있는지 확인 (URL 기반 중복 체크)
                existing_article = self.supabase_manager.client.table('articles').select('id').eq('url', url).execute()
                if existing_article.data:
                    return True  # 이미 존재하는 기사
                
                # 기사 페이지 내용 가져오기
                html_content = await self.get_page_content(session, url)
                if not html_content:
                    return False
                
                # 제목과 본문 추출
                result = self.extract_article_content(html_content, url)
                if not result or len(result) != 3:
                    return False
                
                title, content, publish_date = result
                
                # 제목 기반 중복 체크도 추가
                existing_title = self.supabase_manager.client.table('articles').select('id').eq('title', title).execute()
                if existing_title.data:
                    console.print(f"[yellow]중복 제목 발견, 건너뜀: {title[:50]}...[/yellow]")
                    return True  # 중복이지만 성공으로 처리
                
                # 새 기사 삽입
                article_data = {
                    'title': title,
                    'url': url,
                    'content': content,
                    'published_at': publish_date,
                    'media_id': self.media_id,  # 미리 가져온 media_id 사용
                    'bias': self.media_bias,   # bias 명시적 설정
                    'issue_id': 6  # 임시 issue_id
                }
                
                result = self.supabase_manager.insert_article(article_data)
                if result:
                    console.print(f"[green]✅ 새 기사 저장: {title[:50]}...[/green]")
                    return True
                else:
                    console.print(f"[red]❌ 기사 저장 실패: {title[:50]}...[/red]")
                    return False
                
            except Exception as e:
                logger.error(f"기사 처리 실패 ({url}): {e}")
                return False

    async def crawl_articles(self, article_links):
        """기사들을 동시에 크롤링합니다."""
        console.print(f"\n📰 {len(article_links)}개 기사 크롤링 시작...")
        
        # 세션 설정 - 성능 최적화
        connector = aiohttp.TCPConnector(limit=200, limit_per_host=50)
        timeout = aiohttp.ClientTimeout(total=self.timeout, connect=3)
        
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
        
        console.print("🚀 뉴스1 정치 기사 크롤러 시작!")
        console.print(f"📅 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # 세션 설정
        connector = aiohttp.TCPConnector(limit=200, limit_per_host=50)
        timeout = aiohttp.ClientTimeout(total=self.timeout, connect=3)
        
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            all_article_links = []
            
            # 1. HTML 파싱으로 초기 기사 수집 (100개 보장)
            console.print("🔍 1단계: HTML 파싱으로 기사 수집 (100개 목표)...")
            initial_links = await self.collect_article_links_fallback(session)
            all_article_links.extend(initial_links)
            console.print(f"📄 초기 기사: {len(initial_links)}개 수집")
            
            # 2. Ajax API로 추가 기사 수집
            console.print("🔍 2단계: Ajax API로 추가 기사 수집...")
            api_links = await self.collect_article_links_via_api(session)
            all_article_links.extend(api_links)
            console.print(f"📄 API 기사: {len(api_links)}개 수집")
            
            # 3. 중복 제거
            all_article_links = list(set(all_article_links))
            console.print(f"📄 중복 제거 후 총: {len(all_article_links)}개 기사")
            
            # 4. 100개 미달 시 추가 크롤링
            target_count = 100
            if len(all_article_links) < target_count:
                shortage = target_count - len(all_article_links)
                console.print(f"🔍 3단계: {shortage}개 부족, 추가 크롤링 실행...")
                
                # 더 많은 더보기 클릭으로 추가 수집
                try:
                    additional_links = await self._collect_with_playwright_enhanced(
                        self.politics_url, 
                        shortage + 20  # 여유분 추가
                    )
                    
                    # 중복 체크 후 추가
                    new_links = [link for link in additional_links if link not in all_article_links]
                    all_article_links.extend(new_links)
                    all_article_links = list(set(all_article_links))  # 최종 중복 제거
                    
                    console.print(f"📄 추가 크롤링: {len(new_links)}개 새 기사 수집")
                    console.print(f"📄 최종 총: {len(all_article_links)}개 기사")
                    
                except Exception as e:
                    console.print(f"[red]추가 크롤링 실패: {str(e)}[/red]")
            
            if len(all_article_links) >= target_count:
                console.print(f"✅ 100개 목표 달성! ({len(all_article_links)}개)")
            else:
                console.print(f"⚠️  목표 미달: {len(all_article_links)}개 ({target_count - len(all_article_links)}개 부족)")
                console.print("📄 사용 가능한 기사로 크롤링 계속 진행...")
            
            if not all_article_links:
                console.print("❌ 수집할 기사가 없습니다.")
                return
            
            # 4. 기사 크롤링
            success_count, failed_count = await self.crawl_articles(all_article_links)
        
        # 결과 요약
        end_time = datetime.now()
        duration = end_time - start_time
        
        # 결과 테이블 생성
        table = Table(title="뉴스1 크롤링 결과", box=box.ROUNDED)
        table.add_column("항목", style="cyan", no_wrap=True)
        table.add_column("값", style="magenta")
        
        table.add_row("총 기사 수", str(len(all_article_links)))
        table.add_row("성공", f"{success_count}개", style="green")
        table.add_row("실패", f"{failed_count}개", style="red")
        table.add_row("성공률", f"{(success_count/len(all_article_links)*100):.1f}%")
        table.add_row("소요 시간", f"{duration.total_seconds():.2f}초")
        table.add_row("평균 속도", f"{len(all_article_links)/duration.total_seconds():.2f} 기사/초")
        
        console.print(table)
        console.print(f"✅ 뉴스1 크롤링 완료! 🎉")

async def main():
    """메인 함수"""
    crawler = News1PoliticsCrawler()
    await crawler.run()

if __name__ == "__main__":
    asyncio.run(main())
