import asyncio
import aiohttp
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
import hashlib
from typing import List, Dict, Set, Optional
import logging
import json
from datetime import datetime
import re

class AdvancedNewsCrawler:
    def __init__(self, config: Dict):
        self.config = config
        self.console = Console()
        self.session = None
        self.visited_urls: Set[str] = set()
        self.news_data: List[Dict] = []
        self.duplicate_checker = set()
        self.stats = {
            'start_time': None,
            'end_time': None,
            'total_urls': 0,
            'successful_crawls': 0,
            'failed_crawls': 0,
            'total_news': 0
        }
        
        # 로깅 설정
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('crawler.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    async def __aenter__(self):
        timeout_config = aiohttp.ClientTimeout(total=self.config['timeout'])
        connector = aiohttp.TCPConnector(limit=100, limit_per_host=30)
        self.session = aiohttp.ClientSession(
            timeout=timeout_config,
            connector=connector,
            headers={'User-Agent': self.config['user_agent']}
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _generate_hash(self, title: str, content: str) -> str:
        """향상된 중복 체크를 위한 해시 생성"""
        # 특수문자 제거 및 정규화
        normalized_title = re.sub(r'[^\w\s]', '', title.lower().strip())
        normalized_content = re.sub(r'[^\w\s]', '', content.lower().strip())
        
        # 제목과 내용의 첫 100자만 사용하여 해시 생성
        text = f"{normalized_title[:100]}{normalized_content[:100]}"
        return hashlib.md5(text.encode()).hexdigest()
    
    def _is_duplicate(self, title: str, content: str) -> bool:
        """향상된 중복 뉴스 체크"""
        content_hash = self._generate_hash(title, content)
        if content_hash in self.duplicate_checker:
            return True
        self.duplicate_checker.add(content_hash)
        return False
    
    async def fetch_page(self, url: str, retries: int = 0) -> Optional[str]:
        """웹페이지 비동기 페칭 with 재시도 로직"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                elif response.status == 429:  # Rate limit
                    if retries < self.config['max_retries']:
                        await asyncio.sleep(2 ** retries)  # 지수 백오프
                        return await self.fetch_page(url, retries + 1)
                    else:
                        self.logger.warning(f"Rate limit exceeded: {url}")
                        return None
                else:
                    self.logger.warning(f"HTTP {response.status}: {url}")
                    return None
        except asyncio.TimeoutError:
            if retries < self.config['max_retries']:
                await asyncio.sleep(1)
                return await self.fetch_page(url, retries + 1)
            else:
                self.logger.error(f"타임아웃: {url}")
                return None
        except Exception as e:
            self.logger.error(f"에러 발생 {url}: {str(e)}")
            return None
    
    def parse_news(self, html: str, base_url: str) -> List[Dict]:
        """향상된 HTML 파싱"""
        soup = BeautifulSoup(html, 'lxml')
        news_items = []
        
        # 더 정교한 선택자 패턴
        selectors = [
            # 일반적인 뉴스 구조
            'article', '.news-item', '.article', '.post', '.story',
            '[class*="news"]', '[class*="article"]', '[class*="post"]', '[class*="story"]',
            # 언론사별 특화 선택자
            '.news-list li', '.article-list .item', '.post-list .post',
            '.news-content', '.article-content', '.post-content'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    try:
                        # 제목 추출 (다양한 패턴)
                        title = self._extract_title(element)
                        
                        # 내용 추출
                        content = self._extract_content(element)
                        
                        # 링크 추출
                        link = self._extract_link(element, base_url)
                        
                        # 날짜 추출
                        date = self._extract_date(element)
                        
                        # 이미지 추출
                        image = self._extract_image(element, base_url)
                        
                        if title and content and not self._is_duplicate(title, content):
                            news_items.append({
                                'title': title,
                                'content': content[:300] + '...' if len(content) > 300 else content,
                                'link': link,
                                'source': urlparse(base_url).netloc,
                                'date': date,
                                'image': image,
                                'crawled_at': datetime.now().isoformat()
                            })
                    except Exception as e:
                        self.logger.debug(f"파싱 에러: {str(e)}")
                        continue
        
        return news_items
    
    def _extract_title(self, element) -> str:
        """제목 추출 로직"""
        # 우선순위별 제목 추출
        title_selectors = [
            'h1', 'h2', 'h3', 'h4',
            '[class*="title"]', '[class*="headline"]', '[class*="subject"]',
            '.title', '.headline', '.subject'
        ]
        
        for selector in title_selectors:
            title_elem = element.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title and len(title) > 5:  # 의미있는 제목인지 확인
                    return title
        
        return ""
    
    def _extract_content(self, element) -> str:
        """내용 추출 로직"""
        # 우선순위별 내용 추출
        content_selectors = [
            '[class*="content"]', '[class*="body"]', '[class*="text"]',
            '.content', '.body', '.text', 'p'
        ]
        
        for selector in content_selectors:
            content_elem = element.select_one(selector)
            if content_elem:
                content = content_elem.get_text(strip=True)
                if content and len(content) > 20:  # 의미있는 내용인지 확인
                    return content
        
        return ""
    
    def _extract_link(self, element, base_url: str) -> str:
        """링크 추출 로직"""
        link_elem = element.find('a')
        if link_elem and link_elem.get('href'):
            return urljoin(base_url, link_elem.get('href'))
        return ""
    
    def _extract_date(self, element) -> str:
        """날짜 추출 로직"""
        date_selectors = [
            '[class*="date"]', '[class*="time"]', '[datetime]',
            '.date', '.time', 'time'
        ]
        
        for selector in date_selectors:
            date_elem = element.select_one(selector)
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                if date_text:
                    return date_text
                # datetime 속성 확인
                datetime_attr = date_elem.get('datetime')
                if datetime_attr:
                    return datetime_attr
        
        return ""
    
    def _extract_image(self, element, base_url: str) -> str:
        """이미지 추출 로직"""
        img_elem = element.find('img')
        if img_elem and img_elem.get('src'):
            return urljoin(base_url, img_elem.get('src'))
        return ""
    
    async def crawl_urls(self, urls: List[str]) -> List[Dict]:
        """URL 목록을 병렬로 크롤링"""
        self.stats['start_time'] = datetime.now()
        self.stats['total_urls'] = len(urls)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console
        ) as progress:
            
            task = progress.add_task("크롤링 진행률...", total=len(urls))
            
            # ThreadPoolExecutor로 병렬 처리
            with ThreadPoolExecutor(max_workers=self.config['max_workers']) as executor:
                loop = asyncio.get_event_loop()
                futures = []
                
                for url in urls:
                    if url not in self.visited_urls:
                        self.visited_urls.add(url)
                        future = loop.run_in_executor(executor, lambda u=url: asyncio.run(self._crawl_single_url(u)))
                        futures.append(future)
                
                # 결과 수집
                for future in asyncio.as_completed(futures):
                    try:
                        result = await future
                        if result:
                            self.news_data.extend(result)
                            self.stats['successful_crawls'] += 1
                        else:
                            self.stats['failed_crawls'] += 1
                        progress.advance(task)
                        
                        # 진행률 업데이트
                        progress.update(task, description=f"크롤링 진행률... ({len(self.news_data)}개 뉴스 수집)")
                        
                    except Exception as e:
                        self.logger.error(f"크롤링 에러: {str(e)}")
                        self.stats['failed_crawls'] += 1
                        progress.advance(task)
        
        self.stats['end_time'] = datetime.now()
        self.stats['total_news'] = len(self.news_data)
        
        elapsed_time = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        self.console.print(f"\n✅ 크롤링 완료! 소요시간: {elapsed_time:.2f}초")
        
        return self.news_data
    
    async def _crawl_single_url(self, url: str) -> List[Dict]:
        """단일 URL 크롤링"""
        html = await self.fetch_page(url)
        if html:
            await asyncio.sleep(self.config['delay_between_requests'])  # 요청 간 지연
            return self.parse_news(html, url)
        return []
    
    def display_results(self):
        """향상된 결과 표시"""
        if not self.news_data:
            self.console.print("❌ 크롤링된 뉴스가 없습니다.")
            return
        
        # 통계 정보
        elapsed_time = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
        stats_panel = Panel(
            f"총 {self.stats['total_news']}개의 뉴스 수집\n"
            f"성공: {self.stats['successful_crawls']}개 | 실패: {self.stats['failed_crawls']}개\n"
            f"중복 제거: {len(self.duplicate_checker)}개\n"
            f"방문한 URL: {len(self.visited_urls)}개\n"
            f"소요시간: {elapsed_time:.2f}초",
            title="📊 크롤링 통계",
            border_style="blue"
        )
        self.console.print(stats_panel)
        
        # 뉴스 테이블
        table = Table(title="📰 수집된 뉴스")
        table.add_column("제목", style="cyan", width=35)
        table.add_column("내용", style="white", width=50)
        table.add_column("출처", style="green", width=15)
        table.add_column("날짜", style="yellow", width=15)
        table.add_column("링크", style="blue", width=25)
        
        for news in self.news_data[:25]:  # 상위 25개 표시
            table.add_row(
                news['title'][:35] + '...' if len(news['title']) > 35 else news['title'],
                news['content'][:50] + '...' if len(news['content']) > 50 else news['content'],
                news['source'],
                news['date'][:15] if news['date'] else "N/A",
                news['link'][:25] + '...' if len(news['link']) > 25 else news['link']
            )
        
        self.console.print(table)
    
    def save_results(self, filename: str = None):
        """결과를 파일로 저장"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"crawled_news_{timestamp}.json"
        
        data_to_save = {
            'metadata': {
                'crawled_at': datetime.now().isoformat(),
                'stats': self.stats,
                'config': self.config
            },
            'news_data': self.news_data
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data_to_save, f, ensure_ascii=False, indent=2)
        
        self.console.print(f"💾 결과가 '{filename}' 파일로 저장되었습니다.")

async def main():
    """메인 실행 함수"""
    from config import CRAWLER_CONFIG, NEWS_SOURCES
    
    console = Console()
    console.print(Panel("🚀 고급 언론사 크롤러 시작", style="bold blue"))
    
    # 모든 언론사 URL 수집
    all_urls = []
    for category, urls in NEWS_SOURCES.items():
        all_urls.extend(urls)
        console.print(f"📰 {category}: {len(urls)}개 언론사")
    
    console.print(f"\n총 {len(all_urls)}개 언론사에서 크롤링을 시작합니다.\n")
    
    async with AdvancedNewsCrawler(CRAWLER_CONFIG) as crawler:
        news_data = await crawler.crawl_urls(all_urls)
        crawler.display_results()
        crawler.save_results()

if __name__ == "__main__":
    asyncio.run(main())

```

```

