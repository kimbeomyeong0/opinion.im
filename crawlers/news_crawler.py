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
import hashlib
from typing import List, Dict, Set
import logging

class NewsCrawler:
    def __init__(self, max_workers: int = 10, timeout: int = 10):
        self.max_workers = max_workers
        self.timeout = timeout
        self.console = Console()
        self.session = None
        self.visited_urls: Set[str] = set()
        self.news_data: List[Dict] = []
        self.duplicate_checker = set()
        
        # 로깅 설정
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    async def __aenter__(self):
        timeout_config = aiohttp.ClientTimeout(total=self.timeout)
        self.session = aiohttp.ClientSession(timeout=timeout_config)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _generate_hash(self, title: str, content: str) -> str:
        """중복 체크를 위한 해시 생성"""
        text = f"{title}{content}".lower().strip()
        return hashlib.md5(text.encode()).hexdigest()
    
    def _is_duplicate(self, title: str, content: str) -> bool:
        """중복 뉴스 체크"""
        content_hash = self._generate_hash(title, content)
        if content_hash in self.duplicate_checker:
            return True
        self.duplicate_checker.add(content_hash)
        return False
    
    async def fetch_page(self, url: str) -> str:
        """웹페이지 비동기 페칭"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    self.logger.warning(f"HTTP {response.status}: {url}")
                    return ""
        except asyncio.TimeoutError:
            self.logger.error(f"타임아웃: {url}")
            return ""
        except Exception as e:
            self.logger.error(f"에러 발생 {url}: {str(e)}")
            return ""
    
    def parse_news(self, html: str, base_url: str) -> List[Dict]:
        """HTML에서 뉴스 데이터 파싱"""
        soup = BeautifulSoup(html, 'html.parser')
        news_items = []
        
        # 일반적인 뉴스 구조 패턴들
        selectors = [
            'article', '.news-item', '.article', '.post',
            '[class*="news"]', '[class*="article"]', '[class*="post"]'
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    try:
                        # 제목 추출
                        title_elem = element.find(['h1', 'h2', 'h3', 'h4']) or element.find(class_=lambda x: x and ('title' in x.lower() or 'headline' in x.lower()))
                        title = title_elem.get_text(strip=True) if title_elem else ""
                        
                        # 내용 추출
                        content_elem = element.find(['p', 'div']) or element.find(class_=lambda x: x and ('content' in x.lower() or 'body' in x.lower()))
                        content = content_elem.get_text(strip=True) if content_elem else ""
                        
                        # 링크 추출
                        link_elem = element.find('a')
                        link = urljoin(base_url, link_elem.get('href', '')) if link_elem else ""
                        
                        if title and content and not self._is_duplicate(title, content):
                            news_items.append({
                                'title': title,
                                'content': content[:200] + '...' if len(content) > 200 else content,
                                'link': link,
                                'source': urlparse(base_url).netloc
                            })
                    except Exception as e:
                        self.logger.debug(f"파싱 에러: {str(e)}")
                        continue
        
        return news_items
    
    async def crawl_urls(self, urls: List[str]) -> List[Dict]:
        """URL 목록을 병렬로 크롤링"""
        start_time = time.time()
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        ) as progress:
            
            task = progress.add_task("크롤링 진행률...", total=len(urls))
            
            # ThreadPoolExecutor로 병렬 처리
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 비동기 작업을 동기적으로 실행
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
                        progress.advance(task)
                    except Exception as e:
                        self.logger.error(f"크롤링 에러: {str(e)}")
                        progress.advance(task)
        
        elapsed_time = time.time() - start_time
        self.console.print(f"\n✅ 크롤링 완료! 소요시간: {elapsed_time:.2f}초")
        
        return self.news_data
    
    async def _crawl_single_url(self, url: str) -> List[Dict]:
        """단일 URL 크롤링"""
        html = await self.fetch_page(url)
        if html:
            return self.parse_news(html, url)
        return []
    
    def display_results(self):
        """결과를 Rich로 표시"""
        if not self.news_data:
            self.console.print("❌ 크롤링된 뉴스가 없습니다.")
            return
        
        # 통계 정보
        stats_panel = Panel(
            f"총 {len(self.news_data)}개의 뉴스 수집\n"
            f"중복 제거: {len(self.duplicate_checker)}개\n"
            f"방문한 URL: {len(self.visited_urls)}개",
            title="📊 크롤링 통계",
            border_style="blue"
        )
        self.console.print(stats_panel)
        
        # 뉴스 테이블
        table = Table(title="📰 수집된 뉴스")
        table.add_column("제목", style="cyan", width=40)
        table.add_column("내용", style="white", width=60)
        table.add_column("출처", style="green", width=20)
        table.add_column("링크", style="blue", width=30)
        
        for news in self.news_data[:20]:  # 상위 20개만 표시
            table.add_row(
                news['title'][:40] + '...' if len(news['title']) > 40 else news['title'],
                news['content'][:60] + '...' if len(news['content']) > 60 else news['content'],
                news['source'],
                news['link'][:30] + '...' if len(news['link']) > 30 else news['link']
            )
        
        self.console.print(table)

async def main():
    """메인 실행 함수"""
    # 테스트용 언론사 URL들
    test_urls = [
        "https://www.yna.co.kr/",
        "https://www.hani.co.kr/",
        "https://www.khan.co.kr/",
        "https://www.donga.com/",
        "https://www.chosun.com/",
        "https://www.joongang.co.kr/",
        "https://www.seoul.co.kr/",
        "https://www.kmib.co.kr/",
        "https://www.munhwa.com/",
        "https://www.kyunghyang.com/"
    ]
    
    console = Console()
    console.print(Panel("🚀 언론사 크롤러 시작", style="bold blue"))
    
    async with NewsCrawler(max_workers=8, timeout=10) as crawler:
        news_data = await crawler.crawl_urls(test_urls)
        crawler.display_results()
        
        # 결과 저장
        if news_data:
            import json
            with open('crawled_news.json', 'w', encoding='utf-8') as f:
                json.dump(news_data, f, ensure_ascii=False, indent=2)
            console.print("💾 결과가 'crawled_news.json' 파일로 저장되었습니다.")

if __name__ == "__main__":
    asyncio.run(main())

