#!/usr/bin/env python3
"""
중앙일보 정치 기사 크롤러
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

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

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JoongangPoliticsCrawler:
    def __init__(self, max_articles: int = 100):
        self.base_url = "https://www.joongang.co.kr"
        self.politics_url = "https://www.joongang.co.kr/politics"
        self.max_articles = max_articles
        self.console = Console()
        self.delay = 0.1
        
        # 중앙일보는 중도 성향
        self.media_name = "중앙일보"
        self.media_bias = "Right"  # media_outlets 테이블의 값과 정확히 일치
        
        # Supabase 매니저 초기화
        try:
            self.supabase_manager = UnifiedSupabaseManager()
            self.console.print("[green]Supabase 클라이언트 초기화 성공[/green]")
        except Exception as e:
            self.console.print(f"[red]Supabase 초기화 실패: {str(e)}[/red]")
            raise

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
                logger.info("기본 이슈 생성 성공")
                return True
            else:
                logger.info("기본 이슈가 이미 존재합니다")
                return True

        except Exception as e:
            logger.error(f"기본 이슈 생성 실패: {str(e)}")
            return False

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
                'media_id': 5,  # 중앙일보 media_id
                'title': article_data['title'],
                'url': article_data['url'],
                'content': article_data['content'],
                'bias': self.media_bias,
                'published_at': published_at
            }
            
            # Supabase에 저장
            result = self.supabase_manager.client.table('articles').insert(insert_data).execute()
            
            if result.data:
                logger.info(f"기사 저장 성공: {article_data['title'][:50]}...")
                return True
            else:
                logger.error(f"기사 저장 실패: {article_data['title'][:50]}...")
                return False
                
        except Exception as e:
            logger.error(f"기사 저장 중 오류 발생: {str(e)}")
            return False
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
    
    async def get_politics_article_links(self) -> List[str]:
        """정치 섹션에서 기사 링크 수집 (페이지네이션 방식)"""
        all_article_links = []
        
        # 페이지네이션을 통한 기사 수집
        max_pages = 10  # 최대 10페이지까지 시도
        articles_per_page = 25  # 중앙일보는 페이지당 약 25개 기사
        
        for page in range(1, max_pages + 1):
            page_url = f"{self.politics_url}?page={page}"
            self.console.print(f"[cyan]🔍 {page}페이지 크롤링: {page_url}[/cyan]")
            
            try:
                page_links = await self._get_links_from_page(page_url)
                all_article_links.extend(page_links)
                self.console.print(f"[green]  - {page}페이지에서 {len(page_links)}개 링크 발견[/green]")
                
                # 충분한 기사를 수집했으면 중단
                if len(all_article_links) >= self.max_articles:
                    break
                    
                await asyncio.sleep(self.delay)
                
            except Exception as e:
                self.console.print(f"[red]  - {page}페이지 크롤링 실패: {str(e)}[/red]")
                logger.error(f"{page}페이지 크롤링 실패: {str(e)}")
                continue
        
        # 중복 제거 및 정리
        unique_links = list(set(all_article_links))
        valid_links = [link for link in unique_links if self._is_valid_article_url(link)]
        valid_links.sort(reverse=True)
        
        self.console.print(f"[bold green]총 {len(valid_links)}개 정치 기사 링크 발견[/bold green]")
        return valid_links[:self.max_articles]
    
    async def _get_links_from_page(self, url: str) -> List[str]:
        """특정 페이지에서 기사 링크 수집"""
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return []
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                article_links = []
                
                # story_list 안의 card에서 기사 링크 추출
                cards = soup.select('.story_list .card')
                for card in cards:
                    headline_link = card.select_one('.headline a')
                    if headline_link:
                        href = headline_link.get('href')
                        if href:
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
    
    def _is_valid_article_url(self, url: str) -> bool:
        """유효한 기사 URL인지 확인"""
        if not url:
            return False
        
        # 중앙일보 기사 URL 패턴 확인
        if '/article/' not in url:
            return False
        
        # URL 길이 확인 (너무 짧으면 제외)
        if len(url) < 30:
            return False
        
        return True
    
    async def crawl_article(self, url: str) -> Optional[Dict]:
        """개별 기사 크롤링"""
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # 기사 정보 추출
                title = self._extract_title(soup)
                content = self._extract_content(soup)
                published_time = self._extract_published_time(soup)
                
                if not title or not content:
                    return None
                
                return {
                    'title': title,
                    'url': url,
                    'content': content,
                    'published_at': published_time
                }
                
        except Exception as e:
            logger.error(f"기사 {url} 크롤링 실패: {str(e)}")
            return None
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """기사 제목 추출"""
        try:
            # 중앙일보 제목 선택자
            title_selectors = [
                'h1.headline',
                '.headline h1',
                'h1.title',
                '.title h1',
                'h1'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    if title and len(title) > 5:
                        return title
            
            return None
            
        except Exception as e:
            logger.error(f"제목 추출 실패: {str(e)}")
            return None
    
    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        """기사 본문 추출"""
        try:
            # 중앙일보 본문 선택자
            content_selectors = [
                '.article_body',
                '.article-content',
                '.content',
                '.body',
                'article',
                '.article'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    # 불필요한 요소 제거
                    for elem in content_elem.select('script, style, .ad, .advertisement'):
                        elem.decompose()
                    
                    content = content_elem.get_text(strip=True, separator=' ')
                    if content and len(content) > 100:
                        return content
            
            return None
            
        except Exception as e:
            logger.error(f"본문 추출 실패: {str(e)}")
            return None
    
    def _extract_published_time(self, soup: BeautifulSoup) -> Optional[datetime]:
        """기사 발행 시간 추출"""
        try:
            # 중앙일보 시간 선택자
            time_selectors = [
                'meta[name="article:published_time"]',
                '.date',
                '.published_date',
                '.article_date',
                '.time'
            ]
            
            for selector in time_selectors:
                if selector.startswith('meta'):
                    time_elem = soup.select_one(selector)
                    if time_elem:
                        time_str = time_elem.get('content')
                        if time_str:
                            try:
                                # ISO 8601 형식 파싱
                                return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                            except:
                                pass
                else:
                    time_elem = soup.select_one(selector)
                    if time_elem:
                        time_str = time_elem.get_text(strip=True)
                        if time_str:
                            # 중앙일보 날짜 형식: "2025.08.20 22:48"
                            try:
                                return datetime.strptime(time_str, '%Y.%m.%d %H:%M')
                            except:
                                pass
            
            return None
            
        except Exception as e:
            logger.error(f"발행 시간 추출 실패: {str(e)}")
            return None
    
    async def save_to_database(self, articles: List[Dict]) -> None:
        """데이터베이스에 기사 저장"""
        if not articles:
            return
        
        self.console.print("\n데이터베이스에 저장 중...")
        
        # 기본 이슈 생성 확인
        await self.create_default_issue()
        
        # 기사 저장
        saved_count = 0
        for article in articles:
            try:
                # 기존 기사 확인
                existing = self.supabase_manager.client.table('articles').select('id').eq('url', article['url']).execute()
                
                if existing.data:
                    # 기존 기사 업데이트
                    self.supabase_manager.client.table('articles').update({
                        'title': article['title'],
                        'content': article['content'],
                        'published_at': article['published_at'].isoformat() if article['published_at'] else None
                    }).eq('url', article['url']).execute()
                    
                    self.console.print(f"[yellow]기존 기사 업데이트: {article['title'][:50]}...[/yellow]")
                else:
                    # 새 기사 삽입
                    self.supabase_manager.insert_article({
                        'issue_id': 1,  # 기본 이슈 ID 사용
                        'media_id': 5,  # 중앙일보 media_id
                        'title': article['title'],
                        'url': article['url'],
                        'content': article['content'],
                        'bias': self.media_bias,  # media_outlets 테이블의 값과 정확히 일치
                        'published_at': article['published_at']
                    })
                    
                    saved_count += 1
                    self.console.print(f"[green]새 기사 삽입: {article['title'][:50]}...[/green]")
                
            except Exception as e:
                logger.error(f"기사 저장 실패: {str(e)}")
                continue
        
        self.console.print(f"[bold green]✅ {saved_count}개 기사 저장 성공![/bold green]")
        
        # 이슈 편향성 업데이트
        try:
            self.supabase_manager.update_issue_bias(1)  # 기본 이슈 ID 사용
            self.console.print(f"[green]이슈 편향성 업데이트 성공: 1[/green]")
        except Exception as e:
            logger.error(f"이슈 편향성 업데이트 실패: {str(e)}")
    
    def display_results(self, articles: List[Dict], elapsed_time: float) -> None:
        """크롤링 결과 표시"""
        if not articles:
            self.console.print("[red]크롤링된 기사가 없습니다.[/red]")
            return
        
        # 결과 요약
        success_count = len(articles)
        failed_count = self.max_articles - success_count
        speed = success_count / elapsed_time if elapsed_time > 0 else 0
        
        summary_panel = Panel(
            f"⏱️  크롤링 시간: {elapsed_time:.2f}초\n"
            f"📰 발견된 기사: {self.max_articles}개\n"
            f"✅ 성공: {success_count}개\n"
            f"❌ 실패: {failed_count}개\n"
            f"🚀 속도: {speed:.1f} 기사/초",
            title="📊 크롤링 결과",
            border_style="blue"
        )
        
        self.console.print(summary_panel)
        
        # 기사 목록 테이블
        table = Table(title="📰 크롤링된 기사 목록")
        table.add_column("번호", style="cyan", no_wrap=True)
        table.add_column("제목", style="white")
        table.add_column("길이", style="green")
        table.add_column("시간", style="yellow")
        
        for i, article in enumerate(articles[:20], 1):  # 처음 20개만 표시
            title = article['title'][:50] + "..." if len(article['title']) > 50 else article['title']
            content_length = len(article['content']) if article['content'] else 0
            published_time = article['published_at'].strftime('%Y-%m-%d\n%H:%M') if article['published_at'] else "N/A"
            
            table.add_row(
                str(i),
                title,
                f"{content_length:,}자",
                published_time
            )
        
        if len(articles) > 20:
            table.add_row("...", f"및 {len(articles) - 20}개 더", "", "")
        
        self.console.print(table)
    
    async def run(self) -> None:
        """크롤러 실행"""
        start_time = time.time()
        
        # 제목 출력
        title_panel = Panel(
            "중앙일보 정치 기사 크롤러\n"
            "🚀 최신 정치 기사 100개를 빠르게 수집합니다",
            title="중앙일보 정치 기사 크롤러",
            border_style="green"
        )
        self.console.print(title_panel)
        
        # 1단계: 기사 링크 수집
        self.console.print("\n🔍 정치 기사 링크 수집 중...")
        article_links = await self.get_politics_article_links()
        
        if not article_links:
            self.console.print("[red]수집된 기사 링크가 없습니다.[/red]")
            return
        
        # 2단계: 기사 크롤링
        self.console.print(f"\n📰 {len(article_links)}개 기사 크롤링 시작...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("기사 크롤링 중...", total=len(article_links))
            
            articles = []
            for link in article_links:
                article = await self.crawl_article(link)
                if article:
                    articles.append(article)
                
                progress.advance(task)
                await asyncio.sleep(self.delay)
        
        # 3단계: 결과 표시
        elapsed_time = time.time() - start_time
        self.display_results(articles, elapsed_time)
        
        # 4단계: 데이터베이스 저장
        if articles:
            await self.save_to_database(articles)
        
        self.console.print("\n🎉 크롤링 완료!")


    async def collect_all_articles(self) -> List[Dict]:
        """모든 기사 수집 (표준 인터페이스)"""
        try:
            result = await self.crawl_article()
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
    async with JoongangPoliticsCrawler(max_articles=100) as crawler:
        await crawler.run()

if __name__ == "__main__":
    asyncio.run(main())
