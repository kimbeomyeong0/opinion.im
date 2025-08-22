import asyncio
import aiohttp
import time
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.columns import Columns
from datetime import datetime
import re
from urllib.parse import urljoin, urlparse
import logging
from utils.supabase_manager_unified import UnifiedSupabaseManager
import json
from playwright.async_api import async_playwright

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChosunPoliticsCrawler:
    def __init__(self):
        self.console = Console()
        self.supabase = UnifiedSupabaseManager()
        self.base_url = "https://www.chosun.com"
        self.politics_url = "https://www.chosun.com/politics/"
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 크롤링 설정
        self.max_articles = 100
        self.max_workers = 20  # 동시 요청 수
        self.timeout = 5  # 요청 타임아웃
        self.delay = 0.1  # 요청 간 지연
        
        # 결과 저장
        self.articles = []
        self.stats = {
            'total_found': 0,
            'successful': 0,
            'failed': 0,
            'start_time': None,
            'end_time': None
        }
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        connector = aiohttp.TCPConnector(limit=self.max_workers, limit_per_host=10)
        timeout = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()
    
    async def get_politics_article_links(self) -> List[str]:
        """정치 섹션에서 기사 링크 수집 (여러 카테고리 포함)"""
        all_article_links = []
        
        # 크롤링할 정치 카테고리들
        politics_categories = [
            '',  # 메인 정치 페이지
            'politics_general/',  # 정치일반
            'blue_house/',        # 청와대  
            'assembly/',          # 국회
            'diplomacy-defense/', # 외교국방
            'north_korea/',       # 북한
        ]
        
        # Playwright를 사용한 "기사 더보기" 기능 활용
        self.console.print(f"[cyan]🔍 Playwright로 '기사 더보기' 기능 활용 중...[/cyan]")
        try:
            more_links = await self._get_more_articles_with_playwright()
            all_article_links.extend(more_links)
            self.console.print(f"[green]  - Playwright '더보기'에서 {len(more_links)}개 추가 링크 발견[/green]")
        except Exception as e:
            self.console.print(f"[red]  - Playwright '더보기' 크롤링 실패: {str(e)}[/red]")
        
        # 날짜별 추가 페이지들 (최근 2주)
        from datetime import datetime, timedelta
        today = datetime.now()
        for i in range(14):  # 최근 2주
            date = today - timedelta(days=i)
            date_str = date.strftime('%Y/%m/%d')
            
            # 각 카테고리별로 날짜 페이지 추가
            for main_category in ['politics_general', 'blue_house', 'assembly', 'diplomacy-defense']:
                date_url = f"{main_category}/{date_str}/"
                politics_categories.append(date_url)
                
            # 메인 정치 페이지의 날짜별 페이지도 시도
            main_date_url = f"{date_str}/"
            politics_categories.append(main_date_url)
        
        for category in politics_categories:
            category_url = f"{self.politics_url}{category}"
            self.console.print(f"[cyan]🔍 {category_url} 크롤링 중...[/cyan]")
            
            try:
                category_links = await self._get_links_from_page(category_url)
                all_article_links.extend(category_links)
                self.console.print(f"[green]  - {len(category_links)}개 링크 발견[/green]")
                
                # 요청 간 딜레이
                await asyncio.sleep(self.delay)
                
            except Exception as e:
                self.console.print(f"[red]  - {category} 크롤링 실패: {str(e)}[/red]")
                logger.error(f"{category} 크롤링 실패: {str(e)}")
                continue
        
        # 중복 제거 및 정리
        unique_links = list(set(all_article_links))
        valid_links = [link for link in unique_links if self._is_valid_article_url(link)]
        
        # 최신 기사 우선 정렬 (URL에 날짜가 포함되어 있으므로)
        valid_links.sort(reverse=True)
        
        self.console.print(f"[bold green]총 {len(valid_links)}개 정치 기사 링크 발견[/bold green]")
        return valid_links[:self.max_articles]
    
    async def _get_links_from_page(self, url: str) -> List[str]:
        """특정 페이지에서 기사 링크 수집 (더보기 기능 포함)"""
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                article_links = []
                
                # 방법 1: feed-item 안의 기사 링크 추출 (가장 정확)
                feed_items = soup.select('.feed-item')
                for item in feed_items:
                    headline_link = item.select_one('.story-card__headline[href*="/politics/"]')
                    if headline_link:
                        href = headline_link.get('href')
                        if href:
                            if href.startswith('/'):
                                full_url = urljoin(self.base_url, href)
                            else:
                                full_url = href
                            if full_url not in article_links and self._is_valid_article_url(full_url):
                                article_links.append(full_url)
                
                # 방법 2: story-card-component 클래스를 가진 div 안의 링크
                story_cards = soup.select('.story-card-component a[href*="/politics/"]')
                for link in story_cards:
                    href = link.get('href')
                    if href and '/politics/' in href:
                        if href.startswith('/'):
                            full_url = urljoin(self.base_url, href)
                        else:
                            full_url = href
                        if full_url not in article_links:
                            article_links.append(full_url)
                
                # 방법 3: 모든 정치 관련 링크
                all_links = soup.find_all('a', href=True)
                for link in all_links:
                    href = link.get('href')
                    if href and '/politics/' in href and len(href) > 20:
                        if href.startswith('/'):
                            full_url = urljoin(self.base_url, href)
                        else:
                            full_url = href
                        if full_url not in article_links and self._is_valid_article_url(full_url):
                            article_links.append(full_url)
                
                # 방법 4: 특정 클래스나 구조 기반 링크 추출
                content_links = soup.select('a[href*="/2025/"], a[href*="/2024/"]')
                for link in content_links:
                    href = link.get('href')
                    if href and '/politics/' in href:
                        if href.startswith('/'):
                            full_url = urljoin(self.base_url, href)
                        else:
                            full_url = href
                        if full_url not in article_links and self._is_valid_article_url(full_url):
                            article_links.append(full_url)
                
                return article_links
                
        except Exception as e:
            logger.error(f"페이지 {url} 링크 수집 실패: {str(e)}")
            return []
    

    
    async def _get_more_articles_with_playwright(self) -> List[str]:
        """Playwright를 사용하여 '기사 더보기' 버튼을 클릭하고 추가 기사 수집"""
        additional_links = []
        
        try:
            async with async_playwright() as p:
                # 브라우저 실행 (headless 모드)
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                
                # 조선일보 정치 페이지 접속
                await page.goto(self.politics_url, wait_until='networkidle')
                
                # 초기 기사 수 확인
                initial_articles = await page.query_selector_all('.feed-item')
                self.console.print(f"[cyan]  - 초기 기사 수: {len(initial_articles)}개[/cyan]")
                
                # "기사 더보기" 버튼을 여러 번 클릭하여 더 많은 기사 로드
                max_clicks = 10  # 최대 10번 클릭 시도
                click_count = 0
                
                for i in range(max_clicks):
                    try:
                        # "기사 더보기" 버튼 찾기
                        load_more_button = await page.query_selector('#load-more-stories')
                        
                        if load_more_button:
                            # 버튼이 보이는지 확인
                            is_visible = await load_more_button.is_visible()
                            
                            if is_visible:
                                # 버튼 클릭
                                await load_more_button.click()
                                click_count += 1
                                
                                # 새로운 기사가 로드될 때까지 대기
                                await page.wait_for_timeout(2000)  # 2초 대기
                                
                                # 현재 기사 수 확인
                                current_articles = await page.query_selector_all('.feed-item')
                                self.console.print(f"[cyan]  - {click_count}번째 클릭 후: {len(current_articles)}개 기사[/cyan]")
                                
                                # 더 이상 기사가 늘어나지 않으면 중단
                                if len(current_articles) <= len(initial_articles):
                                    break
                                    
                                initial_articles = current_articles
                            else:
                                break
                        else:
                            break
                    
            except Exception as e:
                        self.console.print(f"[yellow]  - {i+1}번째 클릭 실패: {str(e)}[/yellow]")
                        break
                
                # 최종적으로 모든 기사 링크 수집
                final_articles = await page.query_selector_all('.feed-item')
                self.console.print(f"[green]  - 최종 기사 수: {len(final_articles)}개[/green]")
                
                # 각 기사에서 링크 추출
                for article in final_articles:
                    try:
                        headline_link = await article.query_selector('.story-card__headline[href*="/politics/"]')
                        if headline_link:
                            href = await headline_link.get_attribute('href')
                            if href:
                                if href.startswith('/'):
                                    full_url = urljoin(self.base_url, href)
                                else:
                                    full_url = href
                                if full_url not in additional_links and self._is_valid_article_url(full_url):
                                    additional_links.append(full_url)
                    except Exception as e:
                continue
                
                await browser.close()
                
        except Exception as e:
            self.console.print(f"[red]  - Playwright 실행 실패: {str(e)}[/red]")
            logger.error(f"Playwright 실행 실패: {str(e)}")
        
        return additional_links
    
    def _is_valid_article_url(self, url: str) -> bool:
        """유효한 기사 URL인지 확인"""
        # 제외할 패턴들
        exclude_patterns = [
            '#', 'javascript:', 'mailto:', 'tel:',
            '/tag/', '/author/', '/category/',
            '/search', '/archive', '/print'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url.lower():
                return False
        
        # 포함해야 할 패턴
        include_patterns = ['/politics/', '/article/']
        has_valid_pattern = any(pattern in url for pattern in include_patterns)
        
        return has_valid_pattern and len(url) > 30
    
    async def crawl_article(self, url: str) -> Optional[Dict]:
        """개별 기사 크롤링"""
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
            # 제목 추출
                title = self._extract_title(soup)
                if not title:
                    return None
            
            # 본문 추출
                content = self._extract_content(soup)
                if not content:
                    return None
                
                # 발행 시간 추출
                published_at = self._extract_published_time(soup)
                
                article_data = {
                'title': title,
                    'url': url,
                'content': content,
                    'published_at': published_at,
                    'media_name': '조선일보'
            }
            
                return article_data
            
        except Exception as e:
            logger.error(f"기사 크롤링 실패 {url}: {str(e)}")
            return None
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """기사 제목 추출"""
        # 1. title 태그에서 추출
        title_elem = soup.find('title')
        if title_elem:
            title = title_elem.get_text(strip=True)
            if title and len(title) > 5:
                return title
        
        # 2. meta og:title에서 추출
        og_title = soup.find('meta', property='og:title')
        if og_title:
            title = og_title.get('content', '')
            if title and len(title) > 5:
                return title
        
        # 3. 기타 제목 요소들
        title_selectors = [
            'h1.article-title',
            'h1.title',
            '.article-header h1',
            'h1',
            '.headline h1'
        ]
        
        for selector in title_selectors:
            title_elem = soup.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title and len(title) > 5:
                    return title
        
        return None
    
    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        """기사 본문 추출"""
        # 1. JavaScript 변수에서 콘텐츠 추출 시도
        scripts = soup.find_all('script')
        for script in scripts:
            if script.string and 'Fusion.globalContent' in script.string:
                try:
                    # content_elements 배열 부분 추출
                    start_idx = script.string.find('"content_elements":[')
                    if start_idx != -1:
                        # 배열의 끝 찾기 (중괄호 균형 맞추기)
                        bracket_count = 0
                        end_idx = start_idx
                        in_string = False
                        escape_next = False
                        
                        for j in range(start_idx, len(script.string)):
                            char = script.string[j]
                            
                            if escape_next:
                                escape_next = False
                                continue
                            
                            if char == '\\':
                                escape_next = True
                                continue
                            
                            if char == '"' and not escape_next:
                                in_string = not in_string
                                continue
                            
                            if not in_string:
                                if char == '[':
                                    bracket_count += 1
                                elif char == ']':
                                    bracket_count -= 1
                                    if bracket_count == 0:
                                        end_idx = j + 1
                        break
                    
                        if end_idx > start_idx:
                            content_elements_str = script.string[start_idx:end_idx]
                            
                            # JSON 파싱 시도
                            try:
                                # content_elements 부분을 JSON으로 파싱
                                content_elements_json = '{' + content_elements_str + '}'
                                parsed = json.loads(content_elements_json)
                                
                                if 'content_elements' in parsed:
                                    elements = parsed['content_elements']
                                    
                                    # 텍스트 콘텐츠 추출
                                    text_contents = []
                                    for elem in elements:
                                        if isinstance(elem, dict) and elem.get('type') == 'text':
                                            content = elem.get('content', '')
                                            if content and len(content) > 10:
                                                text_contents.append(content)
                                    
                                    if text_contents:
                                        content = '\n\n'.join(text_contents)
                                        if len(content) > 100:
                                            return content
                                            
                            except json.JSONDecodeError:
                                continue
                    
                except Exception as e:
                    logger.debug(f"JavaScript 파싱 실패: {str(e)}")
                    continue
        
        # 2. HTML 요소에서 본문 찾기
        content_selectors = [
            '.content', '.body', '.article-content', '.article-body',
            '.text', '.story-content', '.article-text',
            '.content-text', '.story-body',
            'article', '.main-content'
        ]
        
        for selector in content_selectors:
            content_elem = soup.select_one(selector)
            if content_elem:
                # 불필요한 요소 제거
                for elem in content_elem.select('script, style, .ad, .advertisement, .related-articles'):
                    elem.decompose()
                
                content = content_elem.get_text(separator='\n', strip=True)
                if content and len(content) > 100:  # 최소 100자 이상
                    return content
        
        return None
    
    def _extract_published_time(self, soup: BeautifulSoup) -> Optional[datetime]:
        """발행 시간 추출"""
        # 1. meta 태그에서 발행 시간 추출
        time_meta = soup.find('meta', {'name': 'article:published_time'})
        if time_meta:
            time_str = time_meta.get('content', '')
            if time_str:
                try:
                    # ISO 8601 형식 파싱
                    dt = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    return dt
                except Exception as e:
                    logger.debug(f"시간 파싱 실패: {str(e)}")
                    return None
        
        # 2. 기타 시간 요소들
        time_selectors = [
            '.time', '.date', '.published-time', '.article-time',
            '.story-time', '.timestamp', '.publish-date',
            'time', '.upDate', '.story-date'
        ]
        
        for selector in time_selectors:
            time_elem = soup.select_one(selector)
            if time_elem:
                time_text = time_elem.get_text(strip=True)
                if time_text:
                    # 간단한 시간 형식 파싱 시도
                    try:
                        # 다양한 시간 형식 처리
                        if 'T' in time_text and 'Z' in time_text:
                            # ISO 형식: 2025-08-20T06:05:57.039Z
                            dt = datetime.fromisoformat(time_text.replace('Z', '+00:00'))
                            return dt
                        elif len(time_text) == 19 and time_text.count('-') == 2 and time_text.count(':') == 2:
                            # YYYY-MM-DD HH:MM:SS 형식
                            dt = datetime.strptime(time_text, '%Y-%m-%d %H:%M:%S')
                            return dt
                        elif len(time_text) == 10 and time_text.count('-') == 2:
                            # YYYY-MM-DD 형식
                            dt = datetime.strptime(time_text, '%Y-%m-%d')
                            return dt
                    except Exception as e:
                        logger.debug(f"시간 형식 파싱 실패: {time_text} - {str(e)}")
                        continue
        
        return None
    
    async def crawl_all_articles(self, article_links: List[str]):
        """모든 기사 크롤링"""
        self.stats['start_time'] = time.time()
        
        # 진행률 표시
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            
            task = progress.add_task("기사 크롤링 중...", total=len(article_links))
            
            # 세마포어로 동시 요청 수 제한
            semaphore = asyncio.Semaphore(self.max_workers)
            
            async def crawl_with_semaphore(url):
                async with semaphore:
                    article = await self.crawl_article(url)
                    if article:
                        self.articles.append(article)
                        self.stats['successful'] += 1
                    else:
                        self.stats['failed'] += 1
                    
                    progress.advance(task)
                    
                    # 지연 시간
                    await asyncio.sleep(self.delay)
            
            # 모든 기사 크롤링
            tasks = [crawl_with_semaphore(url) for url in article_links]
            await asyncio.gather(*tasks)
        
        self.stats['end_time'] = time.time()
        self.stats['total_found'] = len(article_links)
    
    def display_results(self):
        """결과 표시"""
        duration = self.stats['end_time'] - self.stats['start_time']
        
        # 통계 패널
        stats_panel = Panel(
            f"⏱️  크롤링 시간: {duration:.2f}초\n"
            f"📰 발견된 기사: {self.stats['total_found']}개\n"
            f"✅ 성공: {self.stats['successful']}개\n"
            f"❌ 실패: {self.stats['failed']}개\n"
            f"🚀 속도: {self.stats['successful']/duration:.1f} 기사/초",
            title="📊 크롤링 결과",
            border_style="green"
        )
        
        self.console.print(stats_panel)
        
        # 성공한 기사 목록
        if self.articles:
            table = Table(title="📰 크롤링된 기사 목록", show_header=True, header_style="bold magenta")
            table.add_column("번호", style="cyan", width=5)
            table.add_column("제목", style="white", width=60)
            table.add_column("길이", style="green", width=10)
            table.add_column("시간", style="yellow", width=15)
            
            for i, article in enumerate(self.articles[:20], 1):  # 상위 20개만 표시
                title = article['title'][:55] + "..." if len(article['title']) > 55 else article['title']
                content_length = len(article['content'])
                
                # 시간 표시 처리
                if article['published_at']:
                    if isinstance(article['published_at'], datetime):
                        time_str = article['published_at'].strftime('%Y-%m-%d %H:%M')
                    else:
                        time_str = str(article['published_at'])
            else:
                    time_str = "시간 정보 없음"
                
                table.add_row(
                    str(i),
                    title,
                    f"{content_length:,}자",
                    time_str
                )
            
            self.console.print(table)
            
            if len(self.articles) > 20:
                self.console.print(f"[dim]... 및 {len(self.articles) - 20}개 더[/dim]")
    
    async def save_to_database(self):
        """데이터베이스에 저장"""
        if not self.articles:
            self.console.print("[yellow]저장할 기사가 없습니다.[/yellow]")
            return
        
        self.console.print("\n[blue]데이터베이스에 저장 중...[/blue]")
        
        # 조선일보 언론사 ID 가져오기
        media_outlet = self.supabase.get_media_outlet('조선일보')
        if not media_outlet:
            self.console.print("[red]조선일보 언론사 정보를 찾을 수 없습니다.[/red]")
            return
        
        media_id = media_outlet['id']
        
        # 크롤링 단계에서는 issue_id를 설정하지 않음 (클러스터링 후 설정)
        # 임시 이슈 ID 6 사용 (데이터베이스 제약조건 준수)
        issue_id = 6
        
        # 기사 데이터 준비
        articles_to_save = []
        for article in self.articles:
            article_data = {
                'issue_id': issue_id,
                'media_id': media_id,
                'title': article['title'],
                'url': article['url'],
                'content': article['content'],
                'bias': media_outlet['bias'],
                'published_at': article['published_at']
            }
            articles_to_save.append(article_data)
        
        # 데이터베이스에 저장
        result = self.supabase.insert_articles_batch(articles_to_save)
        
        if result['success'] > 0:
            self.console.print(f"[green]✅ {result['success']}개 기사 저장 성공![/green]")
        if result['failed'] > 0:
            self.console.print(f"[red]❌ {result['failed']}개 기사 저장 실패[/red]")
        
        # 이슈 편향성 업데이트
        bias_data = {'right': result['success']}  # 조선일보는 우파
        self.supabase.update_issue_bias(issue_id, bias_data)

async def main():
    """메인 함수"""
    console = Console()
    
    # 시작 메시지
    console.print(Panel(
        "[bold blue]조선일보 정치 기사 크롤러[/bold blue]\n"
        "🚀 최신 정치 기사 100개를 빠르게 수집합니다",
        border_style="blue"
    ))
    
    async with ChosunPoliticsCrawler() as crawler:
        # 1. 기사 링크 수집
        console.print("\n[cyan]🔍 정치 기사 링크 수집 중...[/cyan]")
        article_links = await crawler.get_politics_article_links()
        
        if not article_links:
            console.print("[red]기사 링크를 찾을 수 없습니다.[/red]")
            return
        
        # 2. 기사 크롤링
        console.print(f"\n[cyan]📰 {len(article_links)}개 기사 크롤링 시작...[/cyan]")
        await crawler.crawl_all_articles(article_links)
        
        # 3. 결과 표시
        crawler.display_results()
        
        # 4. 데이터베이스 저장
        await crawler.save_to_database()
        
        # 완료 메시지
        console.print("\n[bold green]🎉 크롤링 완료![/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
