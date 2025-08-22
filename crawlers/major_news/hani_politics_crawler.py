#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
한겨레 정치 기사 크롤러
- 최신 정치 기사 100개 수집
- 페이지네이션 활용 (?page={page})
- 20초 내 크롤링 완료 목표
"""

import asyncio
import aiohttp
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
import logging
from utils.supabase_manager_unified import UnifiedSupabaseManager

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HaniPoliticsCrawler:
    """한겨레 정치 기사 크롤러"""
    
    def __init__(self, max_articles: int = 100):
        self.max_articles = max_articles
        self.console = Console()
        self.session: Optional[aiohttp.ClientSession] = None
        self.supabase_manager = UnifiedSupabaseManager()
        
        # 한겨레 설정
        self.base_url = "https://www.hani.co.kr"
        self.politics_url = "https://www.hani.co.kr/arti/politics"
        
        # 통계
        self.total_articles = 0
        self.successful_articles = 0
        self.failed_articles = 0
        self.start_time: Optional[datetime] = None
        
        # 페이지네이션 설정
        self.page_size = 20  # 페이지당 기사 수 (추정)
        self.max_pages = 10  # 최대 페이지 수
        
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()
    
    async def get_politics_article_links(self) -> List[str]:
        """정치 기사 링크 수집"""
        self.console.print("🔍 한겨레 정치 기사 링크 수집 중...")
        
        all_links = set()
        
        try:
            # 1. 메인 페이지에서 기사 수집
            async with self.session.get(self.politics_url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # 기사 링크 추출
                    article_links = soup.select('li.ArticleList_item___OGQO a.BaseArticleCard_link__Q3YFK')
                    for link in article_links:
                        href = link.get('href')
                        if href and href.startswith('/arti/'):
                            full_url = self.base_url + href
                            all_links.add(full_url)
                    
                    self.console.print(f"✅ 메인 페이지: {len(article_links)}개 기사 발견")
            
            # 2. 페이지네이션으로 추가 기사 수집
            for page in range(2, self.max_pages + 1):
                if len(all_links) >= self.max_articles:
                    break
                
                page_url = f"{self.politics_url}?page={page}"
                
                try:
                    async with self.session.get(page_url) as response:
                        if response.status == 200:
                            html = await response.text()
                            soup = BeautifulSoup(html, 'html.parser')
                            
                            # 기사 링크 추출
                            article_links = soup.select('li.ArticleList_item___OGQO a.BaseArticleCard_link__Q3YFK')
                            
                            if not article_links:
                                self.console.print(f"⚠️ 페이지 {page}: 더 이상 기사가 없음")
                                break
                            
                            for link in article_links:
                                href = link.get('href')
                                if href and href.startswith('/arti/'):
                                    full_url = self.base_url + href
                                    all_links.add(full_url)
                            
                            self.console.print(f"📄 페이지 {page}: {len(article_links)}개 기사 발견")
                            
                            # 페이지당 기사 수가 적으면 더 많은 페이지 확인
                            if len(article_links) < self.page_size:
                                break
                                
                        else:
                            self.console.print(f"⚠️ 페이지 {page} 요청 실패: {response.status}")
                            break
                            
                except Exception as e:
                    self.console.print(f"❌ 페이지 {page} 처리 오류: {str(e)}")
                    continue
            
            # 중복 제거 및 최대 개수 제한
            unique_links = list(all_links)[:self.max_articles]
            
            self.console.print(f"🎯 총 {len(unique_links)}개 기사 링크 수집 완료!")
            return unique_links
            
        except Exception as e:
            self.console.print(f"❌ 링크 수집 실패: {str(e)}")
            return []
    
    async def _fetch_article_details(self, article_url: str) -> Optional[Dict[str, Any]]:
        """개별 기사 상세 정보 추출"""
        try:
            async with self.session.get(article_url) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # 제목 추출
                title = None
                title_selectors = [
                    'h1.article-head-headline',
                    'h1.headline',
                    'h1.title',
                    'h2.headline',
                    'h2.title',
                    'title'
                ]
                
                for selector in title_selectors:
                    title_elem = soup.select_one(selector)
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        if title:
                            break
                
                if not title:
                    return None
                
                # 본문 추출
                content = None
                content_selectors = [
                    'div.article-text',
                    'div.article-body',
                    'div.content',
                    'div.body',
                    'article',
                    'div.text'
                ]
                
                for selector in content_selectors:
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        # 불필요한 요소 제거
                        for unwanted in content_elem.select('script, style, .ad, .advertisement, .related, .comment, .article-info, .audio-player, .tts-player, .read-aloud'):
                            unwanted.decompose()
                        
                        content = content_elem.get_text(strip=True, separator='\n')
                        if content and len(content) > 100:  # 최소 100자 이상
                            # 불필요한 텍스트 패턴 제거
                            unwanted_patterns = [
                                '기사를 읽어드립니다',
                                'Your browser does not support the',
                                'audio',
                                'element',
                                '0:00'
                            ]
                            
                            for pattern in unwanted_patterns:
                                content = content.replace(pattern, '')
                            
                            # 연속된 빈 줄 정리
                            content = '\n'.join([line.strip() for line in content.split('\n') if line.strip()])
                            
                            if content and len(content) > 100:
                                break
                
                if not content:
                    return None
                
                # 발행시간 추출
                published_at = None
                time_selectors = [
                    'div.article-date',
                    'div.date',
                    'time',
                    'span.date',
                    'meta[property="article:published_time"]'
                ]
                
                for selector in time_selectors:
                    time_elem = soup.select_one(selector)
                    if time_elem:
                        if selector == 'meta[property="article:published_time"]':
                            time_str = time_elem.get('content', '')
                        else:
                            time_str = time_elem.get_text(strip=True)
                        
                        if time_str:
                            try:
                                # 다양한 시간 형식 파싱
                                if 'T' in time_str:  # ISO 형식
                                    published_at = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                                elif len(time_str) == 19:  # YYYY-MM-DD HH:MM:SS
                                    published_at = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                                elif len(time_str) == 16:  # YYYY-MM-DD HH:MM
                                    published_at = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
                                else:
                                    # 기본값으로 현재 시간 사용
                                    published_at = datetime.now()
                                break
                            except ValueError:
                                continue
                
                if not published_at:
                    published_at = datetime.now()
                
                return {
                    'title': title,
                    'url': article_url,
                    'content': content,
                    'published_at': published_at
                }
                
        except Exception as e:
            logger.error(f"기사 상세 정보 추출 실패 ({article_url}): {str(e)}")
            return None
    
    async def crawl_articles(self) -> None:
        """기사 크롤링 실행"""
        self.start_time = datetime.now()
        
        try:
            # 1단계: 기사 링크 수집
            article_links = await self.get_politics_article_links()
            
            if not article_links:
                self.console.print("[red]수집된 기사 링크가 없습니다.[/red]")
                return
            
            self.total_articles = len(article_links)
            self.console.print(f"\n📰 {self.total_articles}개 기사 크롤링 시작...")
            
            # 2단계: 기사 상세 정보 수집
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
                            media_outlet = self.supabase_manager.get_media_outlet("한겨레")
                            if not media_outlet:
                                media_outlet = self.supabase_manager.create_media_outlet("한겨레", "left")
                            
                            # 기사 저장
                            article_insert_data = {
                                'title': article_data['title'],
                                'url': article_data['url'],
                                'content': article_data['content'],
                                'published_at': article_data['published_at'],
                                'issue_id': issue['id'] if isinstance(issue, dict) else issue,
                                'media_id': media_outlet['id'] if isinstance(media_outlet, dict) else media_outlet,
                                'bias': media_outlet.get('bias', 'left') if isinstance(media_outlet, dict) else 'left'
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
        table = Table(title="📰 한겨레 정치 기사 크롤링 결과")
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
    async with HaniPoliticsCrawler() as crawler:
        await crawler.crawl_articles()

if __name__ == "__main__":
    asyncio.run(main())
