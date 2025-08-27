import asyncio
import aiohttp
import time
import sys
import os
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

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.supabase_manager_unified import UnifiedSupabaseManager
from utils.common.html_parser import HTMLParserUtils

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DongaPoliticsCrawler:
    def __init__(self, max_articles: int = 100):
        self.base_url = "https://www.donga.com"
        self.politics_url = "https://www.donga.com/news/Politics"
        self.max_articles = max_articles
        self.console = Console()
        self.supabase_manager = UnifiedSupabaseManager()
        
        # 동아일보는 우파 언론사
        self.media_name = "동아일보"
        self.media_bias = "Right"
        
    async def get_politics_article_links(self) -> List[str]:
        """동아일보 정치 기사 링크 수집 (페이지네이션 방식)"""
        all_links = []
        
        # 페이지별로 기사 수집
        page = 1
        page_offset = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("동아일보 정치 기사 링크 수집 중...", total=None)
            
            while len(all_links) < self.max_articles:
                if page == 1:
                    url = self.politics_url
                else:
                    # 동아일보 페이지네이션: p=11, p=21, p=31...
                    page_offset = (page - 1) * 10
                    url = f"{self.politics_url}?p={page_offset + 1}&prod=news&ymd=&m="
                
                try:
                    page_links = await self._get_links_from_page(url)
                    if not page_links:
                        self.console.print(f"[yellow]페이지 {page}에서 링크를 찾을 수 없습니다. 중단합니다.[/yellow]")
                        break
                    
                    # 중복 제거하면서 추가
                    new_links = [link for link in page_links if link not in all_links]
                    all_links.extend(new_links)
                    
                    self.console.print(f"[cyan]페이지 {page}: {len(page_links)}개 기사 발견 (총 {len(all_links)}개)[/cyan]")
                    
                    if len(all_links) >= self.max_articles:
                        all_links = all_links[:self.max_articles]
                        break
                    
                    page += 1
                    await asyncio.sleep(0.5)  # 페이지 간 딜레이
                    
                except Exception as e:
                    self.console.print(f"[red]페이지 {page} 처리 중 오류: {str(e)}[/red]")
                    logger.error(f"페이지 {page} 처리 중 오류: {str(e)}")
                    break
        
        self.console.print(f"[green]총 {len(all_links)}개의 동아일보 정치 기사 링크를 수집했습니다![/green]")
        return all_links
    
    async def _get_links_from_page(self, url: str) -> List[str]:
        """특정 페이지에서 기사 링크 추출"""
        links = []
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # 기사 카드 찾기 (모든 섹션)
                        articles = soup.select('.news_card')
                        
                        for article in articles:
                            try:
                                # 제목 링크 찾기
                                title_link = article.select_one('.tit a')
                                if title_link and title_link.get('href'):
                                    href = title_link.get('href')
                                    
                                    # 동아일보 기사 URL 패턴 확인
                                    if '/article/' in href:
                                        full_url = urljoin(self.base_url, href) if href.startswith('/') else href
                                        if self._is_valid_article_url(full_url):
                                            links.append(full_url)
                                            
                            except Exception as e:
                                continue
                                
        except Exception as e:
            logger.error(f"페이지 {url} 처리 중 오류: {str(e)}")
            
        return links
    
    def _is_valid_article_url(self, url: str) -> bool:
        """유효한 기사 URL인지 확인"""
        is_valid = (
            'donga.com' in url and 
            '/article/' in url and
            not url.endswith('.jpg') and
            not url.endswith('.png')
        )
        return is_valid
    
    async def crawl_articles(self, urls: List[str]) -> List[Dict]:
        """기사 내용 크롤링"""
        articles = []
        semaphore = asyncio.Semaphore(10)  # 동시 요청 제한
        
        async def crawl_single_article(url: str) -> Optional[Dict]:
            async with semaphore:
                try:
                    return await self._crawl_single_article(url)
                except Exception as e:
                    logger.error(f"기사 크롤링 실패 {url}: {str(e)}")
                    return None
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("동아일보 기사 내용 크롤링 중...", total=len(urls))
            
            # 동시 실행
            tasks = [crawl_single_article(url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, dict) and result:
                    articles.append(result)
                progress.advance(task)
        
        return articles
    
    async def _crawl_single_article(self, url: str) -> Optional[Dict]:
        """단일 기사 크롤링"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=15) as response:
                    if response.status == 200:
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
                        
                        return {
                            'title': title,
                            'url': url,
                            'content': content,
                            'published_at': published_at
                        }
                        
        except Exception as e:
            logger.error(f"기사 크롤링 실패 {url}: {str(e)}")
            return None
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """기사 제목 추출"""
        try:
            # 동아일보 제목 선택자 (우선순위 순)
            title_selectors = [
                'h1:not(:has(a))',  # 링크가 없는 h1 (로고 제외)
                'title',
                'meta[property="og:title"]'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    if selector == 'title':
                        title = title_elem.get_text(strip=True)
                        # "｜동아일보" 부분 제거
                        if '｜' in title:
                            title = title.split('｜')[0]
                    elif selector == 'meta[property="og:title"]':
                        title = title_elem.get('content', '')
                    else:
                        title = title_elem.get_text(strip=True)
                    
                    if title and len(title) > 5 and title != '동아일보':
                        return title
            
            return None
        except Exception as e:
            logger.error(f"제목 추출 실패: {str(e)}")
            return None
    
    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        """기사 본문 추출"""
        try:
            # 동아일보 본문 선택자 (우선순위 순)
            content_selectors = [
                'section.news_view',
                'meta[property="og:description"]',
                'meta[name="description"]',
                '.article_body',
                '.article_content',
                '.content',
                '.article_txt'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    if selector == 'section.news_view':
                        # 실제 기사 본문에서 광고와 불필요한 요소 제거
                        for unwanted in content_elem.select('.view_ad06, .view_m_adA, .view_m_adB, .view_m_adK, .a1, script, .ad'):
                            unwanted.decompose()
                        
                        # 텍스트 추출 및 정리
                        content = content_elem.get_text(separator='\n', strip=True)
                        
                        # 연속된 줄바꿈 정리
                        content = '\n'.join(line.strip() for line in content.split('\n') if line.strip())
                        
                    elif selector.startswith('meta'):
                        content = content_elem.get('content', '')
                    else:
                        # 불필요한 요소 제거
                        for unwanted in content_elem.select('.advertisement, .related_news, .social_share'):
                            unwanted.decompose()
                        content = content_elem.get_text(strip=True)
                    
                    if content and len(content) > 50:
                        return content
            
            return None
        except Exception as e:
            logger.error(f"본문 추출 실패: {str(e)}")
            return None
    
    def _extract_published_time(self, soup: BeautifulSoup) -> Optional[datetime]:
        """발행 시간 추출"""
        try:
            # 동아일보 시간 선택자 (우선순위 순)
            time_selectors = [
                'meta[property="og:pubdate"]',
                'meta[property="article:published_time"]',
                'meta[property="dd:published_time"]',
                '.article_date',
                '.date',
                '.publish_date'
            ]
            
            for selector in time_selectors:
                time_elem = soup.select_one(selector)
                if time_elem:
                    if selector.startswith('meta'):
                        time_str = time_elem.get('content')
                    else:
                        time_str = time_elem.get_text(strip=True)
                    
                    if time_str:
                        # 다양한 시간 형식 파싱
                        parsed_time = self._parse_time_string(time_str)
                        if parsed_time:
                            return parsed_time
            
            return None
        except Exception as e:
            logger.error(f"시간 추출 실패: {str(e)}")
            return None
    
    def _parse_time_string(self, time_str: str) -> Optional[datetime]:
        """시간 문자열을 datetime 객체로 파싱"""
        try:
            # "1시간 전", "2시간 전" 등의 상대적 시간 처리
            if '시간 전' in time_str:
                hours = int(re.search(r'(\d+)', time_str).group(1))
                from datetime import timedelta
                return datetime.now() - timedelta(hours=hours)
            
            # "2025.08.20 22:48" 형식 처리
            if re.match(r'\d{4}\.\d{2}\.\d{2}', time_str):
                time_str = time_str.replace('.', '-')
                return datetime.strptime(time_str, '%Y-%m-%d %H:%M')
            
            # ISO 형식 처리
            if 'T' in time_str and 'Z' in time_str:
                return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            
            return None
        except Exception as e:
            logger.error(f"시간 파싱 실패: {time_str}, {str(e)}")
            return None
    
    def display_results(self, articles: List[Dict], total_time: float):
        """크롤링 결과 표시"""
        self.console.print("\n" + "="*80)
        self.console.print(f"🎯 동아일보 정치 기사 크롤링 완료!")
        self.console.print("="*80)
        
        # 통계 정보
        stats_table = Table(title="📊 크롤링 통계")
        stats_table.add_column("항목", style="cyan")
        stats_table.add_column("값", style="green")
        
        stats_table.add_row("총 기사 수", str(len(articles)))
        stats_table.add_row("크롤링 시간", f"{total_time:.2f}초")
        stats_table.add_row("평균 속도", f"{len(articles)/total_time:.2f} 기사/초")
        
        self.console.print(stats_table)
        
        # 샘플 기사 표시
        if articles:
            sample_table = Table(title="📰 샘플 기사 (처음 10개)")
            sample_table.add_column("번호", style="cyan")
            sample_table.add_column("제목", style="white")
            sample_table.add_column("URL", style="blue")
            sample_table.add_column("발행시간", style="yellow")
            
            for i, article in enumerate(articles[:10], 1):
                title = article['title'][:50] + "..." if len(article['title']) > 50 else article['title']
                url = article['url'][:60] + "..." if len(article['url']) > 60 else article['url']
                published = article['published_at'].strftime('%Y-%m-%d %H:%M') if article['published_at'] else "N/A"
                
                sample_table.add_row(str(i), title, url, published)
            
            self.console.print(sample_table)
    
    async def save_to_database(self, articles: List[Dict]):
        """데이터베이스에 기사 저장"""
        if not articles:
            self.console.print("[yellow]저장할 기사가 없습니다.[/yellow]")
            return
        
        self.console.print(f"\n💾 {len(articles)}개 기사를 데이터베이스에 저장 중...")
        
        saved_count = 0
        failed_count = 0
        
        for article in articles:
            try:
                # 새로 만든 저장 메서드 사용
                if await self.save_article_to_supabase(article):
                    saved_count += 1
                else:
                    failed_count += 1
                    
            except Exception as e:
                self.console.print(f"[red]기사 저장 실패: {article['title'][:50]}... - {str(e)}[/red]")
                logger.error(f"기사 저장 실패: {str(e)}")
                failed_count += 1
        
        self.console.print(f"\n✅ 총 {saved_count}개 기사가 성공적으로 저장되었습니다!")
        if failed_count > 0:
            self.console.print(f"[red]실패: {failed_count}개[/red]")
    
    async def run(self):
        """크롤러 실행"""
        start_time = time.time()
        
        self.console.print(Panel(
            f"[bold blue]동아일보 정치 기사 크롤러[/bold blue]\n"
            f"목표: [bold green]{self.max_articles}개[/bold green] 기사 수집\n"
            f"언론사: [bold yellow]{self.media_name}[/bold yellow] ({self.media_bias})",
            title="🚀 크롤러 시작",
            border_style="blue"
        ))
        
        try:
            # 1. 기사 링크 수집
            self.console.print("\n🔍 1단계: 동아일보 정치 기사 링크 수집 중...")
            links = await self.get_politics_article_links()
            
            if not links:
                self.console.print("[red]수집된 링크가 없습니다.[/red]")
                return
            
            # 2. 기사 내용 크롤링
            self.console.print(f"\n📰 2단계: {len(links)}개 기사 내용 크롤링 중...")
            articles = await self.crawl_articles(links)
            
            if not articles:
                self.console.print("[red]크롤링된 기사가 없습니다.[/red]")
                return
            
            # 3. 결과 표시
            total_time = time.time() - start_time
            self.display_results(articles, total_time)
            
            # 4. 데이터베이스 저장
            await self.save_to_database(articles)
            
        except Exception as e:
            self.console.print(f"[red]크롤러 실행 중 오류 발생: {str(e)}[/red]")
            logger.error(f"크롤러 실행 중 오류: {str(e)}")


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

    async def create_default_issue(self):
        """기본 이슈를 생성합니다."""
        try:
            # 기존 이슈 확인
            existing = self.supabase_manager.client.table('issues').select('id').eq('id', 1).execute()
            
            if not existing.data:
                # 기본 이슈 생성
                issue_data = {
                    'id': 1,
                    'title': '기본 이슈',
                    'subtitle': '크롤러로 수집된 기사들을 위한 기본 이슈',
                    'summary': '다양한 언론사에서 수집된 정치 관련 기사들을 포함하는 기본 이슈입니다.',
                    'bias_left_pct': 0,
                    'bias_center_pct': 0,
                    'bias_right_pct': 0,
                    'dominant_bias': 'center',
                    'source_count': 0
                }
                
                result = self.supabase_manager.client.table('issues').insert(issue_data).execute()
                self.console.print("✅ 기본 이슈 생성 완료")
            else:
                self.console.print("ℹ️ 기본 이슈가 이미 존재합니다")
                
        except Exception as e:
            self.console.print(f"❌ 기본 이슈 생성 실패: {str(e)}")

    async def save_article_to_supabase(self, article_data: Dict) -> bool:
        """기사를 Supabase에 저장"""
        try:
            # 기본 이슈 생성 확인
            await self.create_default_issue()
            
            # datetime을 문자열로 변환
            published_at = article_data.get('published_at')
            if isinstance(published_at, datetime):
                published_at = published_at.isoformat()
            
            # 기사 데이터 준비
            insert_data = {
                'issue_id': 1,  # 기본 이슈 ID 사용
                'media_id': 2,  # 동아일보 media_id
                'title': article_data['title'],
                'url': article_data['url'],
                'content': article_data['content'],
                'bias': self.media_bias.lower(),
                'published_at': published_at
            }
            
            # 기사 저장
            result = self.supabase_manager.client.table('articles').insert(insert_data).execute()
            
            if result.data:
                self.console.print(f"✅ 기사 저장 성공: {article_data['title'][:30]}...")
                return True
            else:
                self.console.print(f"❌ 기사 저장 실패: {article_data['title'][:30]}...")
                return False
                
        except Exception as e:
            self.console.print(f"❌ 기사 저장 오류: {str(e)}")
            return False

async def main():
    """메인 함수"""
    crawler = DongaPoliticsCrawler(max_articles=100)
    await crawler.run()

if __name__ == "__main__":
    asyncio.run(main())
