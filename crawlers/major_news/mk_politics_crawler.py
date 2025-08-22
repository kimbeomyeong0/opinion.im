#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
매일경제 정치 기사 크롤러
- 20초 내외 빠른 크롤링
- 100개 기사 수집 목표
- 중복 제외
- 중앙일보 크롤러 기반으로 빠른 제작
"""
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
from rich import box
from datetime import datetime
import re
from urllib.parse import urljoin, urlparse
import logging
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'utils'))
from legacy.supabase_manager_v2 import SupabaseManagerV2
import json

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MKPoliticsCrawler:
    def __init__(self, max_articles: int = 100, debug: bool = False):
        self.base_url = "https://www.mk.co.kr"
        self.politics_url = "https://www.mk.co.kr/news/politics/"
        self.max_articles = max_articles
        self.console = Console()
        self.delay = 0.05  # 빠른 크롤링을 위해 딜레이 최소화
        self.debug = debug  # 디버깅 모드
        
        # Supabase 매니저 초기화
        try:
            self.supabase_manager = SupabaseManagerV2()
            self.console.print("[green]Supabase 클라이언트 초기화 성공[/green]")
        except Exception as e:
            self.console.print(f"[red]Supabase 초기화 실패: {str(e)}[/red]")
            raise
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
    
    async def collect_article_links(self) -> List[str]:
        """매일경제 정치 기사 링크를 수집합니다."""
        self.console.print("🔍 매일경제 정치 기사 링크 수집 중...")
        
        all_links = []
        
        # 첫 페이지에서 모든 기사 링크 수집
        try:
            async with self.session.get(self.politics_url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # 더 광범위한 링크 수집
                    # 1. 정치 섹션 링크들
                    politics_links = soup.select('a[href*="/news/politics/"]')
                    
                    # 2. 일반 기사 링크들 
                    general_links = soup.select('a.link')
                    
                    # 3. 추가 정치 관련 링크들
                    additional_links = soup.select('a[href*="/news/"]')
                    
                    # 모든 링크 처리
                    all_candidates = politics_links + general_links + additional_links
                    
                    for link in all_candidates:
                        href = link.get('href')
                        # 정치 섹션만 엄격하게 필터링
                        if href and '/news/politics/' in href and 'politics' in href:
                            if href.startswith('/'):
                                full_url = urljoin(self.base_url, href)
                            else:
                                full_url = href
                            
                            # 정치 카테고리인지 다시 한번 확인
                            if '/politics/' in full_url and full_url not in all_links:
                                all_links.append(full_url)
                    
                    self.console.print(f"📄 매일경제 정치 섹션: {len(all_links)}개 기사 발견")
                    
        except Exception as e:
            self.console.print(f"[red]페이지 로드 실패: {str(e)}[/red]")
        
        # 추가 페이지 수집 (필요시)
        if len(all_links) < 100:  # 100개 미만이면 추가 수집
            for page in range(2, 51):  # 2-50페이지까지 확장
                try:
                    url = f"{self.politics_url}?page={page}"
                    async with self.session.get(url) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, 'html.parser')
                            
                            page_links = soup.select('a[href*="/news/politics/"]')
                            page_count = 0
                            
                            for link in page_links:
                                href = link.get('href')
                                # 정치 섹션만 엄격하게 필터링
                                if href and '/news/politics/' in href and 'politics' in href:
                                    if href.startswith('/'):
                                        full_url = urljoin(self.base_url, href)
                                    else:
                                        full_url = href
                                    
                                    # 정치 카테고리인지 다시 한번 확인
                                    if '/politics/' in full_url and full_url not in all_links:
                                        all_links.append(full_url)
                                        page_count += 1
                            
                            self.console.print(f"📄 페이지 {page}: {page_count}개 새 기사 추가 (총 {len(all_links)}개)")
                            
                            if page_count == 0:
                                break
                                
                            if len(all_links) >= self.max_articles:
                                break
                            
                            await asyncio.sleep(self.delay)
                except Exception as e:
                    self.console.print(f"[red]페이지 {page} 처리 실패: {str(e)}[/red]")
                    break
        
        # 중복 제거
        unique_links = list(set(all_links))
        self.console.print(f"✅ 총 {len(unique_links)}개 기사 링크 수집 완료")
        
        # 100개 미달성시 정치 섹션에서 더보기 버튼으로 추가 수집
        if len(unique_links) < 100:
            self.console.print("🔍 100개 미달성, 정치 섹션에서 더보기 버튼으로 추가 수집...")
            
            try:
                from playwright.async_api import async_playwright
                
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    
                    # 정치 섹션 페이지로 이동
                    await page.goto(self.politics_url)
                    await page.wait_for_load_state('networkidle')
                    
                    # 더보기 버튼을 계속 클릭하여 100개까지 수집
                    clicks = 0
                    max_clicks = 20  # 최대 20번 클릭
                    
                    while len(unique_links) < 100 and clicks < max_clicks:
                        try:
                            # 더보기 버튼 찾기 (다양한 선택자 시도)
                            more_button = None
                            selectors = [
                                'button:has-text("더보기")',
                                'a:has-text("더보기")', 
                                '.more-btn',
                                '.btn-more',
                                '[class*="more"]',
                                'button[class*="more"]'
                            ]
                            
                            for selector in selectors:
                                try:
                                    more_button = page.locator(selector).first
                                    if await more_button.is_visible():
                                        break
                                except:
                                    continue
                            
                            if more_button and await more_button.is_visible():
                                await more_button.click()
                                await page.wait_for_timeout(2000)  # 2초 대기
                                clicks += 1
                                
                                # 새로운 링크들 수집
                                new_links = await page.evaluate('''() => {
                                    const links = Array.from(document.querySelectorAll('a[href*="/news/politics/"]'));
                                    return links.map(link => link.href);
                                }''')
                                
                                # 중복 제거하고 추가
                                for link in new_links:
                                    if link not in unique_links:
                                        unique_links.append(link)
                                
                                self.console.print(f"📄 더보기 클릭 {clicks}번: 총 {len(unique_links)}개 기사")
                                
                                if len(unique_links) >= 100:
                                    break
                            else:
                                self.console.print("📄 더보기 버튼을 찾을 수 없습니다")
                                break
                                
                        except Exception as e:
                            self.console.print(f"[red]더보기 버튼 클릭 실패: {str(e)}[/red]")
                            break
                    
                    await browser.close()
                    
            except ImportError:
                self.console.print("[red]Playwright가 설치되지 않았습니다. pip install playwright 실행 후 playwright install을 실행하세요.[/red]")
            except Exception as e:
                self.console.print(f"[red]Playwright 사용 실패: {str(e)}[/red]")
        
        self.console.print(f"🎯 최종 수집: {len(unique_links)}개 기사")
        return unique_links[:self.max_articles]
    
    async def extract_article_content(self, url: str) -> Optional[Dict]:
        """기사 내용을 추출합니다."""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # 제목 추출: 다양한 선택자 시도
                    title_elem = soup.select_one('h3#text.news_ttl') or soup.select_one('h1.news_ttl') or soup.select_one('.news_ttl')
                    if not title_elem:
                        return None
                    
                    title = title_elem.get_text(strip=True)
                    
                    # 본문 추출: 다양한 선택자 시도
                    content_elems = None
                    
                    # 1차: p[refid] 태그들 (기본)
                    content_elems = soup.select('p[refid]')
                    
                    # 2차: 일반적인 기사 본문 선택자들
                    if not content_elems:
                        content_elems = soup.select('.article_txt p') or soup.select('.news_cnt_detail_wrap p')
                    
                    # 3차: 더 광범위한 본문 선택자들
                    if not content_elems:
                        content_elems = soup.select('.news_cnt p') or soup.select('.article_content p') or soup.select('.content p')
                    
                    # 4차: 모든 p 태그 중 본문으로 보이는 것들
                    if not content_elems:
                        all_p_tags = soup.select('p')
                        content_elems = []
                        for p in all_p_tags:
                            text = p.get_text(strip=True)
                            # 본문으로 보이는 p 태그 필터링 (길이, 내용 등)
                            if len(text) > 20 and not text.startswith('[') and not text.startswith('©'):
                                content_elems.append(p)
                    
                    if not content_elems:
                        if self.debug:
                            self.console.print(f"[yellow]본문 추출 실패 - HTML 구조 확인: {url}[/yellow]")
                            # HTML 구조 일부 출력
                            html_preview = html[:1000] if len(html) > 1000 else html
                            self.console.print(f"[dim]HTML 미리보기: {html_preview}...[/dim]")
                        return None
                    
                    # 모든 문단 텍스트 결합
                    content_parts = [elem.get_text(strip=True) for elem in content_elems if elem.get_text(strip=True)]
                    content = '\n\n'.join(content_parts)
                    
                    if not content.strip():
                        self.console.print(f"[yellow]본문 내용이 비어있음: {url}[/yellow]")
                        return None
                    
                    # 발행일 추출 (기본값 사용)
                    published_at = datetime.now()
                    
                    return {
                        'title': title,
                        'content': content,
                        'url': url,
                        'published_at': published_at
                    }
                    
        except Exception as e:
            self.console.print(f"[red]기사 내용 추출 실패 ({url}): {str(e)}[/red]")
            return None
    
    async def save_to_database(self, article_data: Dict) -> bool:
        """기사를 데이터베이스에 저장합니다."""
        try:
            # 매일경제 언론사 정보 가져오기
            media_outlet = self.supabase_manager.get_media_outlet("매일경제")
            if not media_outlet:
                # 매일경제가 없으면 생성 (보수 성향)
                media_id = self.supabase_manager.create_media_outlet("매일경제", "right")
            else:
                media_id = media_outlet['id']
            
            # 기사 데이터 구성
            processed_data = {
                'title': article_data['title'],
                'content': article_data['content'],
                'url': article_data['url'],
                'published_at': article_data['published_at'].isoformat(),
                'media_id': media_id,
                'bias': 'right',  # 매일경제는 보수 성향
                'issue_id': 6  # 임시 issue_id
            }
            
            # 데이터베이스에 저장
            result = self.supabase_manager.insert_article(processed_data)
            if result:
                self.console.print(f"✅ 기사 저장 성공: {article_data['title'][:50]}...")
                return True
            else:
                self.console.print(f"[red]기사 저장 실패: {article_data['title'][:50]}...[/red]")
                return False
                
        except Exception as e:
            self.console.print(f"[red]데이터베이스 저장 실패: {str(e)}[/red]")
            return False
    
    async def run(self):
        """크롤러를 실행합니다."""
        start_time = time.time()
        self.console.print("🚀 매일경제 정치 기사 크롤러 시작!")
        self.console.print(f"📅 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        try:
            # 1. 기사 링크 수집
            article_links = await self.collect_article_links()
            
            if not article_links:
                self.console.print("❌ 수집할 기사가 없습니다.")
                return
            
            # 2. 기사 내용 수집 및 저장
            self.console.print(f"\n📰 {len(article_links)}개 기사 크롤링 시작...")
            
            successful = 0
            failed = 0
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task("기사 정보 수집 중...", total=len(article_links))
                
                for i, url in enumerate(article_links):
                    try:
                        article_data = await self.extract_article_content(url)
                        if article_data:
                            if await self.save_to_database(article_data):
                                successful += 1
                            else:
                                failed += 1
                        else:
                            failed += 1
                        
                        progress.update(task, advance=1)
                        await asyncio.sleep(self.delay)
                        
                    except Exception as e:
                        self.console.print(f"[red]기사 처리 실패 ({url}): {str(e)}[/red]")
                        failed += 1
                        progress.update(task, advance=1)
            
            # 3. 결과 출력
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            self.console.print("\n" + "="*50)
            self.console.print("      매일경제 크롤링 결과      ")
            self.console.print("="*50)
            
            table = Table(box=box.ROUNDED)
            table.add_column("항목", style="cyan")
            table.add_column("값", style="magenta")
            
            table.add_row("총 기사 수", str(len(article_links)))
            table.add_row("성공", f"{successful}개")
            table.add_row("실패", f"{failed}개")
            table.add_row("성공률", f"{successful/len(article_links)*100:.1f}%")
            table.add_row("소요 시간", f"{elapsed_time:.2f}초")
            table.add_row("평균 속도", f"{len(article_links)/elapsed_time:.2f} 기사/초")
            
            self.console.print(table)
            self.console.print("✅ 매일경제 크롤링 완료! 🎉")
            
        except Exception as e:
            self.console.print(f"[red]크롤러 실행 실패: {str(e)}[/red]")

async def main():
    """메인 함수"""
    # 디버깅 모드로 실행 (본문 추출 실패 원인 확인)
    async with MKPoliticsCrawler(debug=True) as crawler:
        await crawler.run()

if __name__ == "__main__":
    asyncio.run(main())