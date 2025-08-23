#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MBC 정치 섹션 크롤러
- 20초 내에 100개 기사 수집
- 본문을 깔끔하게 추출 (군더더기 제거)
- bias를 올바르게 설정 (media_outlets 테이블 참고)
- 날짜 이동으로 기사 수집
"""

import asyncio
import aiohttp
import time
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.panel import Panel
from datetime import datetime
import re
from urllib.parse import urljoin
import logging
from utils.supabase_manager_unified import UnifiedSupabaseManager
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.common.html_parser import HTMLParserUtils
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MBCPoliticsCrawler:
    def __init__(self):
        self.console = Console()
        self.supabase = UnifiedSupabaseManager()
        self.media_id = 11  # MBC
        self.issue_id = 1  # 기본 이슈 ID
        self.base_url = "https://imnews.imbc.com"
        self.politics_url = "https://imnews.imbc.com/news/2025/politics/"
        self.session: Optional[aiohttp.ClientSession] = None
        
        self.max_articles = 100
        self.max_workers = 15
        self.timeout = 5
        self.delay = 0.05
        
        self.articles = []
        self.collected_articles = set()
        self.stats = {
            'total_found': 0,
            'successful': 0,
            'failed': 0,
            'start_time': None,
            'end_time': None
        }
    
    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=self.max_workers, limit_per_host=8)
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
        if self.session:
            await self.session.close()
    
    async def get_media_outlet(self):
        """미디어 아울렛 정보를 가져옵니다."""
        try:
            result = self.supabase.client.table('media_outlets').select('*').eq('id', self.media_id).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            self.console.print(f"❌ 미디어 아울렛 정보 가져오기 실패: {e}")
            return None
    
    async def get_politics_article_links(self) -> List[str]:
        """날짜 이동으로 기사 링크 수집"""
        self.console.print(f"[cyan]🔍 Playwright로 날짜 이동하며 기사 수집 중...[/cyan]")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                await page.goto(self.politics_url, wait_until='networkidle')
                await page.wait_for_timeout(1500)
                
                article_links = []
                date_count = 0
                max_date_attempts = 25
                
                while len(article_links) < self.max_articles and date_count < max_date_attempts:
                    # 현재 페이지 기사 링크 수집
                    new_links = await self._extract_article_links_from_page(page)
                    article_links.extend(new_links)
                    
                    # 이전 날짜로 이동
                    prev_button = await page.query_selector('a.btn_date.date_prev')
                    if not prev_button:
                        break
                    
                    await prev_button.click()
                    await page.wait_for_timeout(1500)
                    await page.wait_for_load_state('networkidle')
                    
                    date_count += 1
                    if date_count % 5 == 0:
                        self.console.print(f"[yellow]  - {date_count}일 전까지 {len(article_links)}개 기사 발견[/yellow]")
                    
                    if len(article_links) >= self.max_articles:
                        break
                        
            finally:
                await browser.close()
        
        # 중복 제거 및 제한
        unique_links = list(dict.fromkeys(article_links))
        return unique_links[:self.max_articles]
    
    async def _extract_article_links_from_page(self, page) -> List[str]:
        """페이지에서 기사 링크 추출"""
        try:
            article_elements = await page.query_selector_all('a[href*="/article/"]')
            links = []
            
            for element in article_elements:
                href = await element.get_attribute('href')
                if href and '/article/' in href:
                    full_url = urljoin(self.base_url, href)
                    if full_url not in self.collected_articles:
                        links.append(full_url)
                        self.collected_articles.add(full_url)
            
            return links
        except Exception as e:
            return []
    
    async def fetch_article_content(self, url: str) -> Optional[Dict]:
        """기사 내용 가져오기"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    html_content = await response.text()
                    return self.extract_article_content(html_content, url)
                return None
        except Exception as e:
            return None
    
    def extract_article_content(self, html_content: str, url: str) -> Optional[Dict]:
        """기사 본문 추출 및 정리"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        try:
            # 제목 추출
            title = ""
            title_elem = soup.find('span', alt=True)
            if title_elem and title_elem.get('alt'):
                title = title_elem['alt'].replace('&quot;', '"').strip()
            
            if not title:
                title_elem = soup.find('h1') or soup.find('h2') or soup.find('h3')
                if title_elem:
                    title = title_elem.get_text(strip=True)
            
            # 본문 추출
            content = ""
            content_elem = soup.select_one('div.news_txt')
            if content_elem:
                content = content_elem.get_text(strip=True)
            
            if not content:
                content_elem = soup.find('div', class_=re.compile(r'content|body|text|article'))
                if content_elem:
                    content = content_elem.get_text(strip=True)
            
            # 날짜 추출
            publish_date = None
            date_elem = soup.find('span', class_='input')
            if date_elem:
                date_text = date_elem.get_text(strip=True)
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_text)
                if date_match:
                    publish_date = date_match.group(1)
            
            # 불필요한 요소 제거
            unwanted_patterns = [
                r'입력\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}',
                r'수정\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}',
                r'기사제공\s+[^\n]*',
                r'저작권자\s+[^\n]*'
            ]
            
            for pattern in unwanted_patterns:
                content = re.sub(pattern, '', content)
            
            content = re.sub(r'\s+', ' ', content).strip()
            content = re.sub(r'\n+', '\n', content)
            
            if not title or not content:
                return None
            
            return {
                'title': title,
                'content': content,
                'publish_date': publish_date,
                'url': url
            }
            
        except Exception as e:
            return None
    
    async def save_to_supabase(self, article_data: Dict) -> bool:
        """기사를 Supabase에 저장 (올바른 테이블 구조 사용)"""
        try:
            # 미디어 아울렛 정보 가져오기
            media_outlet = await self.get_media_outlet()
            if not media_outlet:
                self.console.print("[red]미디어 아울렛 정보를 가져올 수 없습니다.[/red]")
                return False
            
            # 기존 기사 확인
            existing = self.supabase.client.table('articles').select('id').eq('url', article_data['url']).execute()
            
            if existing.data:
                # 기존 기사 업데이트
                self.supabase.client.table('articles').update({
                    'title': article_data['title'],
                    'content': article_data['content'],
                    'published_at': article_data['publish_date']
                }).eq('url', article_data['url']).execute()
                
                self.console.print(f"[yellow]기존 기사 업데이트: {article_data['title'][:50]}...[/yellow]")
                return True
            else:
                # 새 기사 삽입 (올바른 테이블 구조 사용)
                insert_data = {
                    'issue_id': self.issue_id,
                    'media_id': self.media_id,
                    'title': article_data['title'],
                    'url': article_data['url'],
                    'content': article_data['content'],
                    'bias': media_outlet.get('bias', 'center'),  # media_outlets 테이블의 bias 사용
                    'published_at': article_data['publish_date']
                }
                
                result = self.supabase.client.table('articles').insert(insert_data).execute()
                if result.data:
                    self.console.print(f"[green]기사 저장 성공: {article_data['title'][:50]}...[/green]")
                    return True
                else:
                    self.console.print(f"[red]기사 저장 실패: {article_data['title'][:50]}...[/red]")
                    return False
                
        except Exception as e:
            self.console.print(f"[red]기사 저장 오류: {str(e)}[/red]")
            return False
    
    async def run(self):
        """크롤러 실행"""
        self.stats['start_time'] = time.time()
        
        self.console.print(Panel.fit(
            "[bold cyan]MBC 정치 크롤러 시작[/bold cyan]\n"
            f"목표: {self.max_articles}개 기사 수집\n"
            f"URL: {self.politics_url}\n"
            f"이슈 ID: {self.issue_id}, 미디어 ID: {self.media_id}",
            title="🚀 크롤러 정보"
        ))
        
        try:
            # 1. 기사 링크 수집
            self.console.print("\n[bold yellow]1단계: 기사 링크 수집[/bold yellow]")
            article_links = await self.get_politics_article_links()
            
            if not article_links:
                self.console.print("[red]수집된 기사 링크가 없습니다.[/red]")
                return
            
            self.stats['total_found'] = len(article_links)
            self.console.print(f"[green]총 {len(article_links)}개의 기사 링크를 발견했습니다.[/green]")
            
            # 2. 기사 내용 수집 및 저장
            self.console.print("\n[bold yellow]2단계: 기사 내용 수집 및 저장[/bold yellow]")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self.console
            ) as progress:
                
                task = progress.add_task("기사 수집 중...", total=len(article_links))
                
                for i, url in enumerate(article_links):
                    if len(self.articles) >= self.max_articles:
                        break
                    
                    article_data = await self.fetch_article_content(url)
                    
                    if article_data:
                        if await self.save_to_supabase(article_data):
                            self.articles.append(article_data)
                            self.stats['successful'] += 1
                        else:
                            self.stats['failed'] += 1
                    else:
                        self.stats['failed'] += 1
                    
                    progress.update(task, advance=1)
                    
                    if (i + 1) % 20 == 0:
                        self.console.print(f"[cyan]진행률: {i + 1}/{len(article_links)} (성공: {self.stats['successful']}, 실패: {self.stats['failed']})[/cyan]")
                    
                    await asyncio.sleep(self.delay)
            
            # 3. 결과 요약
            self.stats['end_time'] = time.time()
            duration = self.stats['end_time'] - self.stats['start_time']
            
            self.console.print("\n" + "="*60)
            self.console.print(Panel.fit(
                f"[bold green]크롤링 완료![/bold green]\n\n"
                f"📊 수집 결과:\n"
                f"  • 총 발견: {self.stats['total_found']}개\n"
                f"  • 성공: {self.stats['successful']}개\n"
                f"  • 실패: {self.stats['failed']}개\n"
                f"  • 소요 시간: {duration:.1f}초\n"
                f"  • 속도: {self.stats['successful']/duration:.1f}개/초",
                title=" 최종 결과"
            ))
            
            if duration > 20:
                self.console.print("[yellow]⚠️  목표 시간(20초)을 초과했습니다.[/yellow]")
            else:
                self.console.print("[green]✅ 목표 시간(20초) 내에 완료되었습니다![/green]")
                
        except Exception as e:
            self.console.print(f"[red]크롤러 실행 중 오류 발생: {str(e)}[/red]")
            logger.error(f"크롤러 실행 오류: {str(e)}")


    async def collect_all_articles(self) -> List[Dict]:
        """모든 기사 수집 (표준 인터페이스)"""
        try:
            result = await self.run()
            if hasattr(self, 'articles') and self.articles:
                return self.articles
            elif result:
                return result if isinstance(result, list) else []
            else:
                return []
        except Exception as e:
            print(f"❌ 기사 수집 실패: {str(e)}")
            return getattr(self, 'articles', [])

async def main():
    async with MBCPoliticsCrawler() as crawler:
        await crawler.run()

if __name__ == "__main__":
    asyncio.run(asyncio.run(main()))
