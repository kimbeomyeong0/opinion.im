#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
연합뉴스 정치 기사 크롤러
- 20초 내외 빠른 크롤링
- 100개 기사 수집 목표 (에러 발생 시에도 fallback 전략)
- 3단계 fallback 전략으로 안정성 확보
- 실시간 모니터링 및 성능 분석
- 적응형 딜레이 및 병렬 처리 최적화
"""
import asyncio
import aiohttp
import time
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich import box
from datetime import datetime
import re
from urllib.parse import urljoin, urlparse
import logging
import sys
import os
import statistics
from dataclasses import dataclass
from contextlib import asynccontextmanager

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'utils'))
from utils.supabase_manager_unified import UnifiedSupabaseManager
from utils.common.html_parser import HTMLParserUtils

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class CrawlingMetrics:
    """크롤링 성능 메트릭"""
    start_time: float
    end_time: float
    total_articles: int
    successful_articles: int
    failed_articles: int
    network_errors: int
    parsing_errors: int
    avg_response_time: float
    response_times: List[float]
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time
    
    @property
    def success_rate(self) -> float:
        return (self.successful_articles / self.total_articles * 100) if self.total_articles > 0 else 0
    
    @property
    def articles_per_second(self) -> float:
        return self.successful_articles / self.duration if self.duration > 0 else 0

class YnaPoliticsCrawler:
    """연합뉴스 정치 기사 크롤러"""
    
    def __init__(self, max_articles: int = 100, debug: bool = False):
        self.base_url = "https://www.yna.co.kr"
        self.politics_url = "https://www.yna.co.kr/politics/all"
        self.max_articles = max_articles
        self.console = Console()
        self.debug = debug
        
        # 적응형 딜레이 설정
        self.initial_delay = 0.01
        self.current_delay = self.initial_delay
        self.min_delay = 0.005
        self.max_delay = 0.1
        
        # 성능 메트릭
        self.metrics = None
        self.response_times = []
        
        # Supabase 매니저
        self.supabase_manager = None
        
        # 세션 설정
        self.session = None
        self.connector = None
        
        # 에러 카운터
        self.network_errors = 0
        self.parsing_errors = 0
        
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        # Supabase 매니저 초기화
        self.supabase_manager = UnifiedSupabaseManager()
        
        # HTTP 세션 설정 (최적화된 커넥터)
        self.connector = aiohttp.TCPConnector(
            limit=100,  # 동시 연결 수
            limit_per_host=20,  # 호스트당 최대 연결
            ttl_dns_cache=300,  # DNS 캐시 TTL
            use_dns_cache=True,
            keepalive_timeout=30,
            enable_cleanup_closed=True
        )
        
        timeout = aiohttp.ClientTimeout(total=10, connect=5)
        self.session = aiohttp.ClientSession(
            connector=self.connector,
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
        if self.connector:
            await self.connector.close()
    
    def _adjust_delay(self, response_time: float):
        """응답 시간에 따른 딜레이 자동 조정"""
        if response_time > 2.0:  # 응답이 느리면 딜레이 증가
            self.current_delay = min(self.current_delay * 1.2, self.max_delay)
        elif response_time < 0.5:  # 응답이 빠르면 딜레이 감소
            self.current_delay = max(self.current_delay * 0.8, self.min_delay)
    
    async def _make_request(self, url: str, retries: int = 3) -> Optional[str]:
        """HTTP 요청 실행 (재시도 로직 포함)"""
        for attempt in range(retries):
            try:
                start_time = time.time()
                async with self.session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        response_time = time.time() - start_time
                        self.response_times.append(response_time)
                        self._adjust_delay(response_time)
                        return html
                    else:
                        self.console.print(f"[red]HTTP {response.status}: {url}[/red]")
                        
            except asyncio.TimeoutError:
                self.console.print(f"[yellow]타임아웃 (시도 {attempt + 1}/{retries}): {url}[/yellow]")
                self.network_errors += 1
            except Exception as e:
                self.console.print(f"[red]요청 오류 (시도 {attempt + 1}/{retries}): {url} - {str(e)}[/red]")
                self.network_errors += 1
            
            # 재시도 전 대기
            if attempt < retries - 1:
                await asyncio.sleep(0.5 * (attempt + 1))
        
        return None
    
    async def collect_article_links(self) -> List[str]:
        """기사 링크 수집 (3단계 fallback 전략)"""
        self.console.print("🔍 연합뉴스 정치 기사 링크 수집 중...")
        
        all_links = set()
        page = 1
        max_pages = 20  # 안전장치
        
        # 1단계: 기본 페이지네이션 수집
        while len(all_links) < self.max_articles * 1.5 and page <= max_pages:
            page_url = f"{self.politics_url}/{page}" if page > 1 else self.politics_url
            
            html = await self._make_request(page_url)
            if not html:
                self.console.print(f"[yellow]페이지 {page} 로드 실패, 다음 단계로 진행[/yellow]")
                break
            
            soup = BeautifulSoup(html, 'html.parser')
            links = self._extract_links_from_page(soup)
            
            if not links:
                self.console.print(f"[yellow]페이지 {page}에서 링크를 찾을 수 없음[/yellow]")
                break
            
            new_links = [link for link in links if link not in all_links]
            all_links.update(new_links)
            
            self.console.print(f"📄 페이지 {page}: {len(new_links)}개 새 링크 (총 {len(all_links)}개)")
            
            if len(new_links) == 0:  # 더 이상 새 기사가 없으면 중단
                break
            
            page += 1
            await asyncio.sleep(self.current_delay)
        
        # 2단계: 추가 페이지 수집 (목표 달성하지 못한 경우)
        if len(all_links) < self.max_articles:
            self.console.print(f"[yellow]1단계에서 {len(all_links)}개만 수집, 추가 수집 진행[/yellow]")
            additional_pages = min(10, max_pages - page + 1)
            
            for extra_page in range(page, page + additional_pages):
                if len(all_links) >= self.max_articles * 1.5:
                    break
                    
                page_url = f"{self.politics_url}/{extra_page}"
                html = await self._make_request(page_url)
                
                if html:
                    soup = BeautifulSoup(html, 'html.parser')
                    links = self._extract_links_from_page(soup)
                    new_links = [link for link in links if link not in all_links]
                    all_links.update(new_links)
                    
                    self.console.print(f"📄 추가 페이지 {extra_page}: {len(new_links)}개 새 링크 (총 {len(all_links)}개)")
                    await asyncio.sleep(self.current_delay)
        
        # 3단계: 최종 확인 및 정리 (100개 + 여유분)
        final_links = list(all_links)[:self.max_articles + 20]  # 100개 + 20개 여유분
        
        self.console.print(f"✅ 총 {len(final_links)}개 기사 링크 수집 완료 (목표: 100개)")
        return final_links
    
    def _extract_links_from_page(self, soup: BeautifulSoup) -> List[str]:
        """페이지에서 기사 링크 추출"""
        links = []
        
        # 기본 선택자로 링크 추출
        article_elements = soup.select("li div.news-con strong.tit-news a")
        
        for element in article_elements:
            href = element.get('href')
            if href:
                # 상대 경로를 절대 경로로 변환
                if href.startswith('/'):
                    full_url = urljoin(self.base_url, href)
                else:
                    full_url = href
                
                # 정치 기사 URL인지 확인
                if '/politics/' in full_url or '/view/' in full_url:
                    links.append(full_url)
        
        # fallback: 다른 선택자 시도
        if not links:
            fallback_elements = soup.select("a[href*='/view/']")
            for element in fallback_elements:
                href = element.get('href')
                if href:
                    full_url = urljoin(self.base_url, href)
                    if '/politics/' in full_url or '/view/' in full_url:
                        links.append(full_url)
        
        return links
    
    async def extract_article_content(self, url: str) -> Optional[Dict]:
        """기사 본문 추출 (3단계 fallback 전략)"""
        try:
            html = await self._make_request(url)
            if not html:
                return None
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # 1단계: 기본 선택자로 제목 추출
            title = self._extract_title_fallback(soup)
            if not title:
                if self.debug:
                    self.console.print(f"[yellow]제목 추출 실패: {url}[/yellow]")
                return None
            
            # 2단계: 기본 선택자로 본문 추출
            content = self._extract_content_fallback(soup)
            if not content:
                if self.debug:
                    self.console.print(f"[yellow]본문 추출 실패: {url}[/yellow]")
                return None
            
            # 3단계: 발행일 추출
            published_at = self._extract_published_at_fallback(soup)
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'published_at': published_at
            }
            
        except Exception as e:
            self.parsing_errors += 1
            if self.debug:
                self.console.print(f"[red]기사 추출 오류: {url} - {str(e)}[/red]")
            return None
    
    def _extract_title_fallback(self, soup: BeautifulSoup) -> Optional[str]:
        """제목 추출 (3단계 fallback)"""
        # 1차: 기본 선택자
        title_elem = soup.select_one("strong.tit-news a")
        if title_elem:
            title = title_elem.get_text(strip=True)
            if title and len(title) > 5:
                return title
        
        # 2차: 대안 선택자들
        fallback_selectors = [
            "h1",
            ".title",
            ".headline",
            "meta[property='og:title']",
            "title"
        ]
        
        for selector in fallback_selectors:
            elem = soup.select_one(selector)
            if elem:
                if selector == "meta[property='og:title']":
                    title = elem.get('content', '').strip()
                else:
                    title = elem.get_text(strip=True)
                
                if title and len(title) > 5 and len(title) < 200:
                    return title
        
        return None
    
    def _extract_content_fallback(self, soup: BeautifulSoup) -> Optional[str]:
        """본문 추출 (3단계 fallback)"""
        # 1차: 기본 선택자
        content = self._extract_content_with_selector(soup, "div.story-news.article p")
        if content:
            return content
        
        # 2차: 대안 선택자들
        fallback_selectors = [
            ".article-content p",
            ".news-content p",
            ".content p",
            "article p",
            ".story p"
        ]
        
        for selector in fallback_selectors:
            content = self._extract_content_with_selector(soup, selector)
            if content:
                return content
        
        # 3차: 모든 p 태그에서 추출 (마지막 수단)
        all_paragraphs = soup.find_all('p')
        if all_paragraphs:
            return self._clean_content_from_paragraphs(all_paragraphs)
        
        return None
    
    def _extract_content_with_selector(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        """특정 선택자로 본문 추출"""
        paragraphs = soup.select(selector)
        if paragraphs:
            return self._clean_content_from_paragraphs(paragraphs)
        return None
    
    def _clean_content_from_paragraphs(self, paragraphs: List) -> str:
        """문단에서 본문 정리"""
        content = []
        
        for p in paragraphs:
            txt = p.get_text(strip=True)
            if not txt:
                continue
            
            # 불필요한 내용 필터링
            if any(keyword in txt for keyword in [
                "저작권자", "재배포 금지", "연합뉴스", "yna.co.kr",
                "기자 이메일", "기자 연락처", "광고", "sponsored"
            ]):
                continue
            
            # 이메일 주소 제거
            if "@" in txt and ("@" in txt.split()[-1] or len(txt) < 50):
                continue
            
            # 너무 짧은 텍스트 제거
            if len(txt) < 10:
                continue
            
            content.append(txt)
        
        return "\n\n".join(content) if content else ""
    
    def _extract_published_at_fallback(self, soup: BeautifulSoup) -> Optional[datetime]:
        """발행일 추출 (3단계 fallback)"""
        # 1차: 기본 선택자
        time_elem = soup.select_one("span.time")
        if time_elem:
            time_text = time_elem.get_text(strip=True)
            try:
                # "2025-08-21 21:35" 형식 파싱
                return datetime.strptime(time_text, "%Y-%m-%d %H:%M")
            except ValueError:
                pass
        
        # 2차: 대안 선택자들
        fallback_selectors = [
            ".date",
            ".publish-date",
            ".article-date",
            "meta[property='article:published_time']",
            "time"
        ]
        
        for selector in fallback_selectors:
            elem = soup.select_one(selector)
            if elem:
                if selector == "meta[property='article:published_time']":
                    time_text = elem.get('content', '').strip()
                else:
                    time_text = elem.get_text(strip=True)
                
                if time_text:
                    try:
                        # ISO 형식 파싱 시도
                        return datetime.fromisoformat(time_text.replace('Z', '+00:00'))
                    except ValueError:
                        pass
        
        # 3차: 현재 시간 사용 (fallback)
        return datetime.now()
    
    async def save_to_database(self, article_data: Dict) -> bool:
        """데이터베이스에 기사 저장"""
        try:
            # 연합뉴스 언론사 정보 가져오기
            media_outlet = self.supabase_manager.get_media_outlet("연합뉴스")
            if not media_outlet:
                # 연합뉴스가 없으면 생성
                media_id = self.supabase_manager.create_media_outlet("연합뉴스", "center")
            else:
                media_id = media_outlet['id']
            
            # 기사 데이터 구성
            processed_data = {
                'title': article_data['title'],
                'content': article_data['content'],
                'url': article_data['url'],
                'published_at': article_data['published_at'].isoformat(),
                'media_id': media_id,
                'bias': 'center',  # 연합뉴스는 중도 성향
                'issue_id': 6  # 임시 issue_id
            }
            
            # 중복 확인 (URL로 직접 쿼리)
            try:
                result = self.supabase_manager.client.table('articles').select('id').eq('url', article_data['url']).execute()
                if result.data:
                    return False  # 이미 존재하는 기사
            except Exception as e:
                self.console.print(f"[yellow]중복 확인 실패: {str(e)}[/yellow]")
                # 중복 확인 실패 시에도 기사 저장 시도
            
            # 새 기사 삽입
            article_id = self.supabase_manager.insert_article(processed_data)
            if article_id:
                self.console.print(f"✅ 기사 저장 성공: {article_data['title'][:50]}...")
                return True
            else:
                self.console.print(f"[red]기사 저장 실패: {article_data['title'][:50]}...[/red]")
                return False
                
        except Exception as e:
            self.console.print(f"[red]데이터베이스 저장 오류: {str(e)}[/red]")
            return False
    
    async def run(self):
        """크롤러 실행"""
        start_time = time.time()
        
        self.console.print("🚀 연합뉴스 정치 기사 크롤러 시작!")
        self.console.print(f"📅 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # 1단계: 기사 링크 수집
            article_links = await self.collect_article_links()
            
            if not article_links:
                self.console.print("[red]기사 링크를 수집할 수 없습니다.[/red]")
                return
            
            # 2단계: 기사 본문 크롤링 (100개 달성 시 자동 중단)
            self.console.print(f"📰 {len(article_links)}개 기사 크롤링 시작... (목표: 100개)")
            
            successful_articles = 0
            failed_articles = 0
            target_reached = False  # 100개 달성 플래그
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self.console
            ) as progress:
                
                # 100개 기준으로 진행률 표시
                task = progress.add_task("기사 정보 수집 중... (목표: 100개)", total=100)
                
                # 병렬 처리로 기사 크롤링
                semaphore = asyncio.Semaphore(20)  # 동시 요청 수 제한
                
                async def process_article(link: str):
                    nonlocal successful_articles, failed_articles, target_reached
                    
                    # 100개 달성 시 즉시 중단
                    if target_reached or successful_articles >= 100:
                        return
                    
                    async with semaphore:
                        # 다른 태스크에서 100개 달성했는지 재확인
                        if target_reached or successful_articles >= 100:
                            return
                            
                        article_data = await self.extract_article_content(link)
                        
                        if article_data:
                            if await self.save_to_database(article_data):
                                successful_articles += 1
                                # 100개 달성 시 즉시 중단
                                if successful_articles >= 100:
                                    target_reached = True
                                    self.console.print(f"[green]🎯 목표 기사 수(100개) 달성! 크롤링 중단[/green]")
                                    return
                            else:
                                failed_articles += 1
                        else:
                            failed_articles += 1
                        
                        # 진행률을 100개 기준으로 업데이트
                        if successful_articles <= 100:
                            progress.update(task, completed=successful_articles)
                        await asyncio.sleep(self.current_delay)
                
                # 모든 기사 병렬 처리 (100개 달성 시 자동 중단)
                tasks = [process_article(link) for link in article_links]
                await asyncio.gather(*tasks)
            
            # 3단계: 결과 정리 및 메트릭 계산
            end_time = time.time()
            
            # 100개 달성 시 실제 처리된 기사 수로 메트릭 계산
            actual_processed = min(successful_articles, 100)
            
            self.metrics = CrawlingMetrics(
                start_time=start_time,
                end_time=end_time,
                total_articles=actual_processed,  # 실제 처리된 기사 수
                successful_articles=successful_articles,
                failed_articles=failed_articles,
                network_errors=self.network_errors,
                parsing_errors=self.parsing_errors,
                avg_response_time=statistics.mean(self.response_times) if self.response_times else 0,
                response_times=self.response_times
            )
            
            # 결과 출력
            self._display_results()
            
        except Exception as e:
            self.console.print(f"[red]크롤러 실행 중 오류 발생: {str(e)}[/red]")
            logger.error(f"크롤러 오류: {str(e)}", exc_info=True)
    
    def _display_results(self):
        """크롤링 결과 출력"""
        if not self.metrics:
            return
        
        self.console.print("\n" + "=" * 50)
        self.console.print("      연합뉴스 크롤링 결과      ")
        self.console.print("=" * 50)
        
        # 결과 테이블
        table = Table(box=box.ROUNDED)
        table.add_column("항목", style="cyan", no_wrap=True)
        table.add_column("값", style="magenta")
        
        table.add_row("총 기사 수", str(self.metrics.total_articles))
        table.add_row("성공", f"{self.metrics.successful_articles}개")
        table.add_row("실패", f"{self.metrics.failed_articles}개")
        table.add_row("성공률", f"{self.metrics.success_rate:.1f}%")
        table.add_row("소요 시간", f"{self.metrics.duration:.2f}초")
        table.add_row("평균 속도", f"{self.metrics.articles_per_second:.2f} 기사/초")
        table.add_row("네트워크 오류", str(self.metrics.network_errors))
        table.add_row("파싱 오류", str(self.metrics.parsing_errors))
        
        if self.metrics.response_times:
            table.add_row("평균 응답시간", f"{self.metrics.avg_response_time:.3f}초")
            table.add_row("최소 응답시간", f"{min(self.metrics.response_times):.3f}초")
            table.add_row("최대 응답시간", f"{max(self.metrics.response_times):.3f}초")
        
        self.console.print(table)
        
        # 성능 분석
        # 성능 분석 (100개 기준)
        if self.metrics.duration > 25:
            self.console.print(f"[yellow]⚠️  목표 시간(25초)을 초과했습니다: {self.metrics.duration:.1f}초[/yellow]")
        else:
            self.console.print(f"[green]✅ 목표 시간 내 완료: {self.metrics.duration:.1f}초[/green]")
        
        if self.metrics.successful_articles >= 100:
            self.console.print(f"[green]✅ 목표 기사 수(100개) 달성: {self.metrics.successful_articles}개[/green]")
            if target_reached:
                self.console.print("[blue]💡 100개 달성으로 크롤링이 자동 중단되었습니다.[/blue]")
        else:
            self.console.print(f"[yellow]⚠️  목표 기사 수(100개) 미달성: {self.metrics.successful_articles}개[/yellow]")
        
        self.console.print("✅ 연합뉴스 크롤링 완료! 🎉")


    async def collect_all_articles(self) -> List[Dict]:
        """모든 기사 수집 (표준 인터페이스)"""
        try:
            result = await self.collect_article_links()
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
    async with YnaPoliticsCrawler(debug=False) as crawler:
        await crawler.run()

if __name__ == "__main__":
    asyncio.run(asyncio.run(main()))
