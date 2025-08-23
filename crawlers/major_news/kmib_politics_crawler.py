#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
국민일보 정치 기사 크롤러
- 목표: 100개 정치 기사 수집
- 언론사: 국민일보 (Center)
- 크롤링 시간: 20초 내
"""

import asyncio
import aiohttp
import logging
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Optional, Dict, Any
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.panel import Panel
from utils.supabase_manager_unified import UnifiedSupabaseManager
from urllib.parse import urljoin

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Rich 콘솔 설정
console = Console()

class KMIBPoliticsCrawler:
    def __init__(self):
        self.base_url = "https://www.kmib.co.kr"
        self.politics_url = "https://www.kmib.co.kr/article/listing.asp?sid1=pol"
        self.media_name = "국민일보"
        self.media_bias = "Center"
        self.supabase_manager = UnifiedSupabaseManager()
        self.session = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    def _is_valid_article_url(self, url: str) -> bool:
        """유효한 기사 URL인지 확인"""
        return (
            'kmib.co.kr' in url and
            '/article/view.asp' in url and
            'arcid=' in url and
            not url.endswith('.jpg') and
            not url.endswith('.png')
        )
    
    async def get_politics_article_links(self, target_count: int = 100) -> List[str]:
        """정치 기사 링크 수집 - 100개 목표"""
        article_links = []
        
        with Progress() as progress:
            task = progress.add_task("기사 링크 수집 중...", total=target_count)
            
            # 1. 첫 페이지에서 최상단 고정 기사 5개 수집
            try:
                logger.info("첫 페이지에서 최상단 고정 기사 수집 중...")
                
                async with self.session.get(self.politics_url) as response:
                    if response.status != 200:
                        logger.error(f"첫 페이지 로드 실패: {response.status}")
                        return article_links
                    
                    html = await response.read()
                    try:
                        html = html.decode('euc-kr')
                    except UnicodeDecodeError:
                        try:
                            html = html.decode('cp949')
                        except UnicodeDecodeError:
                            html = html.decode('utf-8', errors='ignore')
                    
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # 최상단 고정 기사 수집 (section.list_main_top)
                    top_section = soup.select_one('section.list_main_top')
                    if top_section:
                        # 왼쪽 메인 기사 1개
                        main_article = top_section.select_one('.col_lg8 .card a')
                        if main_article:
                            href = main_article.get('href')
                            if href and self._is_valid_article_url(href):
                                full_url = urljoin(self.base_url, href)
                                article_links.append(full_url)
                                progress.update(task, completed=len(article_links))
                        
                        # 오른쪽 사이드 기사 4개
                        side_articles = top_section.select('.col_lg4 .card a')
                        for article in side_articles:
                            if len(article_links) >= 5:  # 최상단 고정 기사는 5개만
                                break
                            href = article.get('href')
                            if href and self._is_valid_article_url(href):
                                full_url = urljoin(self.base_url, href)
                                if full_url not in article_links:
                                    article_links.append(full_url)
                                    progress.update(task, completed=len(article_links))
                    
                    logger.info(f"최상단 고정 기사 {len(article_links)}개 수집 완료")
                    
            except Exception as e:
                logger.error(f"최상단 기사 수집 중 오류: {str(e)}")
            
            # 2. 페이지별 변경 기사 수집 (페이지 1부터 시작)
            page = 1
            while len(article_links) < target_count:
                try:
                    # 올바른 페이지네이션 URL 패턴 사용
                    if page == 1:
                        url = f"{self.politics_url}&page={page}"
                    else:
                        url = f"{self.politics_url}&sid2=&page={page}"
                    
                    logger.info(f"페이지 {page} 처리 중: {url}")
                    
                    async with self.session.get(url) as response:
                        if response.status != 200:
                            logger.warning(f"페이지 {page} 로드 실패: {response.status}")
                            break
                        
                        html = await response.read()
                        try:
                            html = html.decode('euc-kr')
                        except UnicodeDecodeError:
                            try:
                                html = html.decode('cp949')
                            except UnicodeDecodeError:
                                html = html.decode('utf-8', errors='ignore')
                        
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        page_article_count = 0
                        
                        # 페이지별 변경 기사 수집 - 모든 기사 링크 찾기
                        all_links = soup.select('a[href*="article/view.asp"]')
                        for link in all_links:
                            if len(article_links) >= target_count:
                                break
                            
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
                        
                        page += 1
                        
                        # 너무 많은 페이지를 탐색하지 않도록 제한 (100개 목표를 위해 15페이지까지)
                        if page > 15:
                            logger.warning("페이지 제한(15)에 도달했습니다.")
                            break
                            
                except Exception as e:
                    logger.error(f"페이지 {page} 처리 중 오류: {str(e)}")
                    break
        
        logger.info(f"총 {len(article_links)}개의 기사 링크를 수집했습니다.")
        return article_links
    
    async def crawl_article(self, url: str) -> Optional[Dict[str, Any]]:
        """개별 기사 크롤링"""
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    return None
                
                # EUC-KR 인코딩으로 읽기
                html = await response.read()
                try:
                    html = html.decode('euc-kr')
                except UnicodeDecodeError:
                    try:
                        html = html.decode('cp949')
                    except UnicodeDecodeError:
                        html = html.decode('utf-8', errors='ignore')
                
                soup = BeautifulSoup(html, 'html.parser')
                
                # 제목 추출
                title = self._extract_title(soup)
                if not title:
                    return None
                
                # 본문 추출
                content = self._extract_content(soup)
                if not content:
                    return None
                
                # 발행시간 추출
                published_at = self._extract_published_time(soup)
                
                return {
                    'title': title,
                    'url': url,
                    'content': content,
                    'published_at': published_at
                }
                
        except Exception as e:
            logger.error(f"기사 크롤링 실패 ({url}): {str(e)}")
            return None
    
    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """기사 제목 추출"""
        try:
            # 우선순위: og:title > meta title > title 태그
            title_selectors = [
                'meta[property="og:title"]',
                'meta[name="title"]',
                'title'
            ]
            
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    if selector.startswith('meta'):
                        title = title_elem.get('content', '')
                    else:
                        title = title_elem.get_text(strip=True)
                    
                    if title and len(title) > 5:
                        # " - 국민일보" 제거
                        title = title.replace(' - 국민일보', '').replace(' - 國民日報', '')
                        return title
            
            return None
        except Exception as e:
            logger.error(f"제목 추출 실패: {str(e)}")
            return None
    
    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        """기사 본문 추출"""
        try:
            # 우선순위: .article_content > .article_body > 메타 태그
            content_selectors = [
                '.article_content',
                '.article_body',
                'meta[property="og:description"]',
                'meta[name="description"]'
            ]
            
            for selector in content_selectors:
                if selector.startswith('meta'):
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        content = content_elem.get('content', '')
                        if content and len(content) > 50:
                            return content
                else:
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        # 불필요한 요소 제거 (광고, 추천기사, 기자정보, 이미지 등)
                        for unwanted in content_elem.select('.advertisement, .ad, .banner, .popup, .share, .layer_popup, .article_recommend, .view_reporter, .view_m_adK, .view_ad06, .view_m_adA, .view_m_adB, .a1, .article_body_img, figure, img, figcaption, .card, .card_body, .card_img, .primary, .tit'):
                            unwanted.decompose()
                        
                        # 모든 script 태그 제거
                        for script in content_elem.find_all('script'):
                            script.decompose()
                        
                        # 모든 style 태그 제거
                        for style in content_elem.find_all('style'):
                            style.decompose()
                        
                        # 텍스트 추출 및 정리 (HTML 태그 완전 제거)
                        content = content_elem.get_text(separator='\n', strip=True)
                        
                        # 줄바꿈 정리 및 빈 줄 제거
                        lines = content.split('\n')
                        clean_lines = []
                        for line in lines:
                            line = line.strip()
                            # 기자 서명 패턴 제거
                            if any(pattern in line for pattern in ['기자,', '기자', 'pan@kmib.co.kr', 'GoodNews paper', '무단전재', 'AI학습 이용 금지', '국민일보(www.kmib.co.kr)', 'kmib.co.kr', '국민일보', '== $0', '추천기사', '기사는 어떠셨나요', '후속기사 원해요', '많이 본 기사', '해당분야별 기사 더보기']):
                                continue
                            # 빈 줄이나 너무 짧은 줄 제거
                            if line and len(line) > 5:
                                clean_lines.append(line)
                        
                        content = '\n'.join(clean_lines)
                        
                        # 마지막 줄에 남은 불필요한 정보 제거
                        if content:
                            lines = content.split('\n')
                            while lines and any(pattern in lines[-1] for pattern in ['국민일보', 'kmib.co.kr', 'www.kmib.co.kr', '== $0']):
                                lines.pop()
                            content = '\n'.join(lines)
                        
                        if content and len(content) > 100:  # 메타 태그보다 긴 본문 요구
                            return content
            
            return None
        except Exception as e:
            logger.error(f"본문 추출 실패: {str(e)}")
            return None
    
    def _extract_published_time(self, soup: BeautifulSoup) -> Optional[datetime]:
        """발행시간 추출"""
        try:
            # article:published_time 메타 태그에서 추출
            time_elem = soup.find('meta', property='article:published_time')
            if time_elem:
                time_str = time_elem.get('content', '')
                if time_str:
                    # ISO 8601 형식 파싱 (예: 2025-08-21T00:04:00+09:00)
                    try:
                        # +09:00 제거 후 파싱
                        if '+' in time_str:
                            time_str = time_str.split('+')[0]
                        return datetime.fromisoformat(time_str)
                    except ValueError:
                        pass
            
            return None
        except Exception as e:
            logger.error(f"발행시간 추출 실패: {str(e)}")
            return None
    
    async def start_crawling(self, target_count: int = 100):
        """크롤링 시작"""
        start_time = datetime.now()
        
        # 시작 메시지
        console.print(Panel(
            f"[bold blue]🚀 크롤러 시작[/bold blue]\n"
            f"국민일보 정치 기사 크롤러\n"
            f"목표: {target_count}개 기사 수집\n"
            f"언론사: {self.media_name} ({self.media_bias})",
            title="국민일보 정치 기사 크롤러",
            border_style="blue"
        ))
        
        # 1단계: 기사 링크 수집
        console.print("\n🔍 1단계: 국민일보 정치 기사 링크 수집 중...")
        article_links = await self.get_politics_article_links(target_count)
        
        if not article_links:
            console.print("❌ 수집된 기사 링크가 없습니다")
            return
        
        # 2단계: 기사 내용 크롤링
        console.print(f"\n📰 2단계: {len(article_links)}개 기사 내용 크롤링 중...")
        
        articles = []
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("국민일보 기사 내용 크롤링 중...", total=len(article_links))
            
            for link in article_links:
                article = await self.crawl_article(link)
                if article:
                    articles.append(article)
                progress.advance(task)
        
        # 결과 통계
        elapsed_time = (datetime.now() - start_time).total_seconds()
        success_rate = len(articles) / len(article_links) * 100
        
        console.print("\n" + "="*80)
        console.print("🎯 국민일보 정치 기사 크롤링 완료!")
        console.print("="*80)
        
        # 통계 테이블
        stats_table = Table(title="📊 크롤링 통계")
        stats_table.add_column("항목", style="cyan")
        stats_table.add_column("값", style="magenta")
        
        stats_table.add_row("총 기사 수", str(len(article_links)))
        stats_table.add_row("성공한 기사 수", str(len(articles)))
        stats_table.add_row("성공률", f"{success_rate:.1f}%")
        stats_table.add_row("크롤링 시간", f"{elapsed_time:.2f}초")
        stats_table.add_row("평균 속도", f"{len(articles)/elapsed_time:.2f} 기사/초")
        
        console.print(stats_table)
        
        # 샘플 기사 테이블
        if articles:
            sample_table = Table(title="📰 샘플 기사 (처음 10개)")
            sample_table.add_column("번호", style="cyan")
            sample_table.add_column("제목", style="green")
            sample_table.add_column("URL", style="blue")
            sample_table.add_column("발행시간", style="yellow")
            
            for i, article in enumerate(articles[:10], 1):
                title = article['title'][:50] + "..." if len(article['title']) > 50 else article['title']
                url = article['url'][:50] + "..." if len(article['url']) > 50 else article['url']
                published_at = article['published_at'].strftime("%Y-%m-%d %H:%M") if article['published_at'] else "N/A"
                
                sample_table.add_row(str(i), title, url, published_at)
            
            console.print(sample_table)
        
        # 데이터베이스 저장
        if articles:
            console.print(f"\n💾 {len(articles)}개 기사를 데이터베이스에 저장 중...")
            await self.save_articles_to_db(articles)
        
        console.print(f"\n✅ 크롤링 완료! 총 {len(articles)}개 기사 처리")
    
    async def save_articles_to_db(self, articles: List[Dict[str, Any]]):
        """기사를 데이터베이스에 저장"""
        saved_count = 0
        
        for article in articles:
            try:
                # 크롤링 단계에서는 issue_id를 설정하지 않음 (클러스터링 후 설정)
                # 임시 이슈 ID 6 사용 (데이터베이스 제약조건 준수)
                issue = {'id': 6}
                
                # 언론사 생성 또는 조회
                media_outlet = self.supabase_manager.get_media_outlet(self.media_name)
                if not media_outlet:
                    media_id = self.supabase_manager.create_media_outlet(self.media_name, self.media_bias)
                    media_outlet = {'id': media_id, 'bias': self.media_bias}
                
                # 중복 기사 확인 (get_article_by_url 메서드가 없으므로 제거)
                # existing_article = self.supabase_manager.get_article_by_url(article['url'])
                # if existing_article:
                #     continue
                
                # 기사 데이터 준비
                article_data = {
                    'issue_id': issue['id'],
                    'media_id': media_outlet['id'],
                    'title': article['title'],
                    'url': article['url'],
                    'content': article['content'],
                    'bias': media_outlet['bias'],
                    'published_at': article['published_at']
                }
                
                # 기사 저장
                self.supabase_manager.insert_article(article_data)
                saved_count += 1
                
                console.print(f"기사 저장 성공: {article['title'][:50]}...")
                
            except Exception as e:
                logger.error(f"기사 저장 실패: {str(e)}")
                continue
        
        console.print(f"✅ {saved_count}개 기사가 성공적으로 저장되었습니다!")


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
    async with KMIBPoliticsCrawler() as crawler:
        await crawler.start_crawling(100)

if __name__ == "__main__":
    asyncio.run(asyncio.run(main()))
