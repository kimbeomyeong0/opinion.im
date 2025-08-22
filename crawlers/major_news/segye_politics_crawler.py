#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
세계일보 정치 기사 크롤러
세계일보의 정치 기사를 크롤링하여 Supabase에 저장합니다.
"""

import asyncio
import aiohttp
import logging
from datetime import datetime
from bs4 import BeautifulSoup
from typing import List, Optional, Dict, Any
from urllib.parse import urljoin, urlparse
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from supabase_manager_v2 import SupabaseManagerV2
from playwright.async_api import async_playwright

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SegyePoliticsCrawler:
    """세계일보 정치 기사 크롤러"""
    
    def __init__(self):
        self.base_url = "https://www.segye.com"
        self.politics_url = "https://www.segye.com/news/politics"
        self.console = Console()
        self.supabase_manager = SupabaseManagerV2()
        
        # 세션 설정
        self.session = None
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 통계
        self.total_articles = 0
        self.successful_articles = 0
        self.failed_articles = 0
        self.start_time = None
        
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.session = aiohttp.ClientSession(headers=self.headers)
        return self
        
    async def __aexit__(self, self_exc_type, self_exc_val, self_exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()
    
    def _is_valid_article_url(self, url: str) -> bool:
        """유효한 기사 URL인지 확인"""
        if not url:
            return False
        
        # 상대 경로인 경우 절대 경로로 변환
        if url.startswith('/'):
            url = urljoin(self.base_url, url)
        
        parsed = urlparse(url)
        return (
            '/newsView/' in url and
            len(url.split('/newsView/')[-1]) > 5  # 기사 ID가 있는지 확인
        )
    
    async def get_politics_article_links(self, target_count: int = 100) -> List[str]:
        """정치 기사 링크 수집 - 100개 목표"""
        article_links = []
        
        with Progress() as progress:
            task = progress.add_task("기사 링크 수집 중...", total=target_count)
            
            # 1. 첫 페이지에서 고정된 Top뉴스 기사 수집
            try:
                logger.info("첫 페이지에서 고정된 Top뉴스 기사 수집 중...")
                
                async with self.session.get(self.politics_url) as response:
                    if response.status != 200:
                        logger.error(f"첫 페이지 로드 실패: {response.status}")
                        return article_links
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # 고정된 Top뉴스 섹션에서 기사 수집
                    top_news_section = soup.select_one('article.newsSubjTop')
                    if top_news_section:
                        top_news_links = top_news_section.select('ul li a')
                        for link in top_news_links:
                            if len(article_links) >= target_count:
                                break
                                
                            href = link.get('href')
                            if href and self._is_valid_article_url(href):
                                full_url = urljoin(self.base_url, href)
                                if full_url not in article_links:
                                    article_links.append(full_url)
                                    progress.update(task, completed=len(article_links))
                    
                    logger.info(f"고정된 Top뉴스에서 {len(article_links)}개 기사 수집 완료")
                    
            except Exception as e:
                logger.error(f"Top뉴스 기사 수집 중 오류: {str(e)}")
            
            # 2. 더 많은 페이지 탐색 (JavaScript 동적 로딩 고려)
            for page in range(1, 21):  # 1~20페이지까지 시도
                if len(article_links) >= target_count:
                    break
                    
                try:
                    url = f"{self.politics_url}?page={page}"
                    logger.info(f"페이지 {page} 처리 중: {url}")
                    
                    async with self.session.get(url) as response:
                        if response.status != 200:
                            logger.warning(f"페이지 {page} 로드 실패: {response.status}")
                            continue
                        
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        page_article_count = 0
                        
                        # 전체 페이지에서 newsView 링크 찾기 (newsSubjTop 제외)
                        all_news_links = soup.select('a[href*="/newsView/"]')
                        
                        for link in all_news_links:
                            if len(article_links) >= target_count:
                                break
                            
                            # newsSubjTop 섹션 내의 링크는 제외 (중복 방지)
                            if link.find_parent('article', class_='newsSubjTop'):
                                continue
                            
                            href = link.get('href')
                            if href and self._is_valid_article_url(href):
                                full_url = urljoin(self.base_url, href)
                                if full_url not in article_links:
                                    article_links.append(full_url)
                                    page_article_count += 1
                                    progress.update(task, completed=len(article_links))
                        
                        logger.info(f"페이지 {page}에서 {page_article_count}개 기사 발견")
                        
                        # 현재 페이지에서 기사를 찾지 못했다면 더 이상 진행하지 않음
                        if page_article_count == 0:
                            logger.info(f"페이지 {page}에서 더 이상 기사를 찾을 수 없습니다.")
                            break
                            
                except Exception as e:
                    logger.error(f"페이지 {page} 처리 중 오류: {str(e)}")
                    continue
            
            # 3. 추가 기사 수집을 위해 다양한 URL 패턴 시도
            if len(article_links) < target_count:
                additional_urls = [
                    "https://www.segye.com/newsList/0101010000000",
                    "https://www.segye.com/newsList/0101010100000", 
                    "https://www.segye.com/newsList/0101010200000",
                    "https://www.segye.com/newsList/0101010300000",
                    "https://www.segye.com/newsList/0101010400000",
                    "https://www.segye.com/newsList/0101010500000",
                    "https://www.segye.com/newsList/0101010600000",
                    "https://www.segye.com/newsList/0101010700000",
                    "https://www.segye.com/newsList/0101010800000",
                    "https://www.segye.com/newsList/0101010900000"
                ]
                
                for url in additional_urls:
                    if len(article_links) >= target_count:
                        break
                        
                    try:
                        logger.info(f"추가 URL 처리 중: {url}")
                        
                        async with self.session.get(url) as response:
                            if response.status == 200:
                                html = await response.text()
                                soup = BeautifulSoup(html, 'html.parser')
                                
                                # newsView 링크 수집
                                news_links = soup.select('a[href*="/newsView/"]')
                                additional_count = 0
                                
                                for link in news_links:
                                    if len(article_links) >= target_count:
                                        break
                                    
                                    href = link.get('href')
                                    if href and self._is_valid_article_url(href):
                                        full_url = urljoin(self.base_url, href)
                                        if full_url not in article_links:
                                            article_links.append(full_url)
                                            additional_count += 1
                                            progress.update(task, completed=len(article_links))
                                
                                logger.info(f"추가 URL에서 {additional_count}개 기사 발견")
                                
                    except Exception as e:
                        logger.error(f"추가 URL 처리 중 오류: {str(e)}")
                        continue
            
            # 4. 마지막 시도: 다른 정치 관련 URL들
            if len(article_links) < target_count:
                final_urls = [
                    "https://www.segye.com/news/politics/list",
                    "https://www.segye.com/news/politics/breaking",
                    "https://www.segye.com/news/politics/analysis",
                    "https://www.segye.com/news/politics/column"
                ]
                
                for url in final_urls:
                    if len(article_links) >= target_count:
                        break
                        
                    try:
                        logger.info(f"최종 URL 처리 중: {url}")
                        
                        async with self.session.get(url) as response:
                            if response.status == 200:
                                html = await response.text()
                                soup = BeautifulSoup(html, 'html.parser')
                                
                                # newsView 링크 수집
                                news_links = soup.select('a[href*="/newsView/"]')
                                final_count = 0
                                
                                for link in news_links:
                                    if len(article_links) >= target_count:
                                        break
                                    
                                    href = link.get('href')
                                    if href and self._is_valid_article_url(href):
                                        full_url = urljoin(self.base_url, href)
                                        if full_url not in article_links:
                                            article_links.append(full_url)
                                            final_count += 1
                                            progress.update(task, completed=len(article_links))
                                
                                logger.info(f"최종 URL에서 {final_count}개 기사 발견")
                                
                    except Exception as e:
                        logger.error(f"최종 URL 처리 중 오류: {str(e)}")
                        continue
        
        logger.info(f"총 {len(article_links)}개의 기사 링크를 수집했습니다.")
        return article_links
    
    async def get_politics_article_links_with_playwright(self, target_count: int = 100) -> List[str]:
        """Playwright를 사용하여 JavaScript 동적 로딩 처리 - 100개 목표"""
        article_links = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            
            try:
                with Progress() as progress:
                    task = progress.add_task("Playwright로 기사 링크 수집 중...", total=target_count)
                    
                    # 1. 첫 페이지에서 고정된 Top뉴스 기사 수집
                    logger.info("첫 페이지에서 고정된 Top뉴스 기사 수집 중...")
                    
                    await page.goto(self.politics_url, wait_until='domcontentloaded', timeout=60000)
                    
                    # 고정된 Top뉴스 섹션에서 기사 수집
                    top_news_links = await page.query_selector_all('article.newsSubjTop ul li a')
                    
                    for link in top_news_links:
                        if len(article_links) >= target_count:
                            break
                            
                        href = await link.get_attribute('href')
                        if href and self._is_valid_article_url(href):
                            full_url = urljoin(self.base_url, href)
                            if full_url not in article_links:
                                article_links.append(full_url)
                                progress.update(task, completed=len(article_links))
                    
                    logger.info(f"고정된 Top뉴스에서 {len(article_links)}개 기사 수집 완료")
                    
                    # 2. 페이지별로 더 많은 기사 수집 (JavaScript 동적 로딩 대기)
                    for page_num in range(1, 21):  # 1~20페이지까지 시도
                        if len(article_links) >= target_count:
                            break
                            
                        try:
                            url = f"{self.politics_url}?page={page_num}"
                            logger.info(f"페이지 {page_num} 처리 중: {url}")
                            
                            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                            
                            # JavaScript 동적 로딩 대기 (기사 목록이 로드될 때까지)
                            await page.wait_for_timeout(3000)  # 3초 대기
                            
                            # 전체 페이지에서 newsView 링크 찾기 (newsSubjTop 제외)
                            all_news_links = await page.query_selector_all('a[href*="/newsView/"]')
                            
                            page_article_count = 0
                            for link in all_news_links:
                                if len(article_links) >= target_count:
                                    break
                                
                                # newsSubjTop 섹션 내의 링크는 제외 (중복 방지)
                                parent_article = await link.query_selector('xpath=ancestor::article[@class="newsSubjTop"]')
                                if parent_article:
                                    continue
                                
                                href = await link.get_attribute('href')
                                if href and self._is_valid_article_url(href):
                                    full_url = urljoin(self.base_url, href)
                                    if full_url not in article_links:
                                        article_links.append(full_url)
                                        page_article_count += 1
                                        progress.update(task, completed=len(article_links))
                            
                            logger.info(f"페이지 {page_num}에서 {page_article_count}개 기사 발견")
                            
                            # 현재 페이지에서 기사를 찾지 못했다면 더 이상 진행하지 않음
                            if page_article_count == 0:
                                logger.info(f"페이지 {page_num}에서 더 이상 기사를 찾을 수 없습니다.")
                                break
                                
                        except Exception as e:
                            logger.error(f"페이지 {page_num} 처리 중 오류: {str(e)}")
                            continue
                    
                    # 3. 추가 기사 수집을 위해 다른 URL들도 시도
                    if len(article_links) < target_count:
                        additional_urls = [
                            "https://www.segye.com/newsList/0101010000000",
                            "https://www.segye.com/newsList/0101010100000", 
                            "https://www.segye.com/newsList/0101010200000",
                            "https://www.segye.com/newsList/0101010300000",
                            "https://www.segye.com/newsList/0101010400000",
                            "https://www.segye.com/newsList/0101010500000"
                        ]
                        
                        for url in additional_urls:
                            if len(article_links) >= target_count:
                                break
                                
                            try:
                                logger.info(f"추가 URL 처리 중: {url}")
                                
                                await page.goto(url, wait_until='domcontentloaded', timeout=60000)
                                await page.wait_for_timeout(2000)  # 2초 대기
                                
                                # newsView 링크 수집
                                news_links = await page.query_selector_all('a[href*="/newsView/"]')
                                additional_count = 0
                                
                                for link in news_links:
                                    if len(article_links) >= target_count:
                                        break
                                    
                                    href = await link.get_attribute('href')
                                    if href and self._is_valid_article_url(href):
                                        full_url = urljoin(self.base_url, href)
                                        if full_url not in article_links:
                                            article_links.append(full_url)
                                            additional_count += 1
                                            progress.update(task, completed=len(article_links))
                                
                                logger.info(f"추가 URL에서 {additional_count}개 기사 발견")
                                
                            except Exception as e:
                                logger.error(f"추가 URL 처리 중 오류: {str(e)}")
                                continue
                    
            finally:
                await browser.close()
        
        logger.info(f"Playwright로 총 {len(article_links)}개의 기사 링크를 수집했습니다.")
        return article_links
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """기사 제목 추출"""
        try:
            # 우선순위: h3#title_sns > title > og:title
            title_selectors = [
                'h3#title_sns',
                'title',
                'meta[property="og:title"]'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    if selector == 'meta[property="og:title"]':
                        title = title_elem.get('content', '')
                    else:
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
            # 우선순위: #article_txt > article.viewBox2 > og:description
            content_selectors = [
                '#article_txt',
                'article.viewBox2',
                'meta[property="og:description"]',
                'meta[name="description"]'
            ]
            
            for selector in content_selectors:
                content_elem = soup.select_one(selector)
                if content_elem:
                    if selector.startswith('meta'):
                        content = content_elem.get('content', '')
                    else:
                        # 불필요한 요소 제거 (광고, 이미지, 기자정보 등)
                        for unwanted in content_elem.select('.image, figure, img, figcaption, .viewInfo, .viewIssue, .precis'):
                            unwanted.decompose()
                        
                        content = content_elem.get_text(separator='\n', strip=True)
                        
                        # 줄바꿈 정리 및 빈 줄 제거
                        lines = content.split('\n')
                        clean_lines = []
                        for line in lines:
                            line = line.strip()
                            # 기자 서명, 저작권, 불필요한 텍스트 패턴 제거
                            if any(pattern in line for pattern in ['기자', 'jm100@segye.com', '세계일보', '무단전재', '재배포 금지', 'ⓒ']):
                                continue
                            # 빈 줄이나 너무 짧은 줄 제거
                            if line and len(line) > 5:
                                clean_lines.append(line)
                        
                        content = '\n'.join(clean_lines)
                    
                    if content and len(content) > 50:
                        return content
            
            return None
        except Exception as e:
            logger.error(f"본문 추출 실패: {str(e)}")
            return None
    
    def _extract_published_time(self, soup: BeautifulSoup) -> Optional[datetime]:
        """기사 작성 시간 추출"""
        try:
            # 우선순위: p.viewInfo > og:article:published_time > meta article:published_time
            time_selectors = [
                'p.viewInfo',
                'meta[property="og:article:published_time"]',
                'meta[property="article:published_time"]'
            ]
            
            for selector in time_selectors:
                time_elem = soup.select_one(selector)
                if time_elem:
                    if selector == 'p.viewInfo':
                        # "입력 : 2025-08-20 17:58:14" 형식에서 추출
                        text = time_elem.get_text()
                        if '입력 :' in text:
                            time_str = text.split('입력 :')[1].split()[0] + ' ' + text.split('입력 :')[1].split()[1]
                            try:
                                return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                            except ValueError:
                                continue
                    else:
                        # ISO 8601 형식
                        time_str = time_elem.get('content', '')
                        if time_str:
                            try:
                                return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                            except ValueError:
                                continue
            
            return None
        except Exception as e:
            logger.error(f"작성시간 추출 실패: {str(e)}")
            return None
    
    async def _fetch_article_details(self, url: str) -> Optional[Dict[str, Any]]:
        """기사 상세 정보 추출"""
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
                
                # 작성시간 추출
                published_at = self._extract_published_time(soup)
                if not published_at:
                    published_at = datetime.now()
                
                return {
                    'title': title,
                    'url': url,
                    'content': content,
                    'published_at': published_at
                }
                
        except Exception as e:
            logger.error(f"기사 상세 정보 추출 실패 ({url}): {str(e)}")
            return None
    
    async def crawl_articles(self):
        """기사 크롤링 실행"""
        self.start_time = datetime.now()
        
        try:
            # 1단계: 기사 링크 수집
            self.console.print("\n📋 1단계: 기사 링크 수집")
            
            # Playwright를 사용하여 JavaScript 동적 로딩 처리
            article_links = await self.get_politics_article_links_with_playwright(target_count=100)
            
            if not article_links:
                self.console.print("❌ 기사 링크를 찾을 수 없습니다.")
                return
            
            self.console.print(f"✓ {len(article_links)}개의 기사 링크를 수집했습니다.")
            
            # 2단계: 기사 상세 정보 수집
            self.console.print("\n📰 2단계: 기사 상세 정보 수집")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("({task.completed}/{task.total})"),
                TimeElapsedColumn(),
                console=self.console
            ) as progress:
                task = progress.add_task("기사 정보 수집 중...", total=len(article_links))
                
                for i, article_url in enumerate(article_links):
                    try:
                        article_data = await self._fetch_article_details(article_url)
                        if article_data:
                            # 크롤링 단계에서는 issue_id를 설정하지 않음 (클러스터링 후 설정)
                            # 임시 이슈 ID 6 사용 (데이터베이스 제약조건 준수)
                            issue = {'id': 6}
                            
                            # 언론사 조회
                            media_outlet = self.supabase_manager.get_media_outlet("세계일보")
                            if not media_outlet:
                                media_outlet = self.supabase_manager.create_media_outlet("세계일보", "center")
                            
                            # 기사 저장
                            article_insert_data = {
                                'title': article_data['title'],
                                'url': article_data['url'],
                                'content': article_data['content'],
                                'published_at': article_data['published_at'],
                                'issue_id': issue['id'] if isinstance(issue, dict) else issue,
                                'media_id': media_outlet['id'] if isinstance(media_outlet, dict) else media_outlet,
                                'bias': media_outlet.get('bias', 'center') if isinstance(media_outlet, dict) else 'center'
                            }
                            
                            self.supabase_manager.insert_article(article_insert_data)
                            logger.info(f"새 기사 삽입: {article_data['title']}")
                            
                            self.successful_articles += 1
                        else:
                            self.failed_articles += 1
                            
                    except Exception as e:
                        logger.error(f"기사 처리 실패 ({article_url}): {str(e)}")
                        self.failed_articles += 1
                    
                    progress.advance(task)
                    
                    # 진행 상황 표시
                    if (i + 1) % 10 == 0:
                        progress.update(task, description=f"기사 정보 수집 중... ({i + 1}/{len(article_links)})")
            
            # 3단계: 결과 표시
            self._display_results()
            
        except Exception as e:
            logger.error(f"크롤링 중 오류 발생: {str(e)}")
            self.console.print(f"❌ 크롤링 중 오류가 발생했습니다: {str(e)}")
        finally:
            if self.session:
                await self.session.close()
    
    def _display_results(self) -> None:
        """크롤링 결과 표시"""
        if not self.start_time:
            return
        
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        # 결과 테이블 생성
        table = Table(title="🌍 세계일보 정치 기사 크롤링 결과")
        table.add_column("항목", style="cyan", no_wrap=True)
        table.add_column("결과", style="magenta")
        
        table.add_row("총 기사 수", str(self.total_articles))
        table.add_row("성공", f"{self.successful_articles}개")
        table.add_row("실패", f"{self.failed_articles}개")
        table.add_row("성공률", f"{(self.successful_articles/self.total_articles*100):.1f}%" if self.total_articles > 0 else "0%")
        table.add_row("소요 시간", f"{duration:.2f}초")
        table.add_row("평균 속도", f"{self.successful_articles/duration:.2f} 기사/초" if duration > 0 else "0 기사/초")
        
        self.console.print(table)
        
        # 성공/실패 요약
        if self.successful_articles > 0:
            self.console.print(f"\n[green]✅ 성공적으로 {self.successful_articles}개의 기사를 수집했습니다![/green]")
        
        if self.failed_articles > 0:
            self.console.print(f"\n[yellow]⚠️ {self.failed_articles}개의 기사 수집에 실패했습니다.[/yellow]")

async def main():
    """메인 함수"""
    async with SegyePoliticsCrawler() as crawler:
        await crawler.crawl_articles()

if __name__ == "__main__":
    asyncio.run(main())
