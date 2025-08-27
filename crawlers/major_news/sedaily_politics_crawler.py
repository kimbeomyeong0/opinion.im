#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
서울경제 정치 기사 크롤러
- 20초 내외 빠른 크롤링
- 100개 기사 수집 목표
- 중복 제거
- 정치 섹션 전용 수집
- aiohttp + BeautifulSoup 기반 빠른 크롤링
"""
import asyncio
import aiohttp
import time
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
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

# 모듈 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.supabase_manager_unified import UnifiedSupabaseManager

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SedailyPoliticsCrawler:
    def __init__(self, max_articles: int = 100, debug: bool = False):
        self.base_url = "https://www.sedaily.com"
        self.politics_url = "https://www.sedaily.com/v/NewsMain/GE"
        self.max_articles = max_articles
        self.console = Console()
        self.delay = 0.02  # 매우 빠른 크롤링을 위해 딜레이 최소화
        self.debug = debug
        
        # 미디어 정보 설정
        self.media_name = "서울경제"
        self.media_bias = "Right"  # 서울경제는 우편향 성향
        self.media_id = None  # media_outlets에서 가져올 예정
        
        # Supabase 매니저 초기화
        try:
            self.supabase_manager = UnifiedSupabaseManager()
            self.console.print("[green]Supabase 클라이언트 초기화 성공[/green]")
            
            # media_outlets에서 서울경제 정보 가져오기
            self._init_media_outlet()
        except Exception as e:
            self.console.print(f"[red]Supabase 초기화 실패: {str(e)}[/red]")
            raise
    
    def _init_media_outlet(self):
        """media_outlets에서 서울경제 정보를 초기화합니다."""
        try:
            media_outlet = self.supabase_manager.get_media_outlet(self.media_name)
            if media_outlet:
                self.media_id = media_outlet['id']
                self.console.print(f"✅ 서울경제 media_id: {self.media_id}, bias: {self.media_bias}")
            else:
                # 서울경제가 없으면 생성
                self.media_id = self.supabase_manager.create_media_outlet(self.media_name, self.media_bias)
                self.console.print(f"✅ 서울경제 생성됨 - media_id: {self.media_id}, bias: {self.media_bias}")
        except Exception as e:
            self.console.print(f"[red]서울경제 media_outlet 초기화 실패: {str(e)}[/red]")
            self.media_id = 15  # 기본값 사용
    
    async def create_default_issue(self):
        """기본 이슈가 존재하는지 확인하고 없으면 생성합니다."""
        try:
            # issues 테이블에서 id=1이 존재하는지 확인
            result = self.supabase_manager.supabase.table('issues').select('id').eq('id', 1).execute()
            
            if not result.data:
                # 기본 이슈가 없으면 생성
                issue_data = {
                    'id': 1,
                    'title': '기본 이슈',
                    'subtitle': '기본 이슈 부제목',
                    'summary': '기본 이슈 요약',
                    'bias_left_pct': 0,
                    'bias_center_pct': 0,
                    'bias_right_pct': 0,
                    'dominant_bias': 'Center',
                    'source_count': 0
                }
                
                self.supabase_manager.supabase.table('issues').insert(issue_data).execute()
                logger.info("기본 이슈가 생성되었습니다")
            else:
                logger.info("기본 이슈가 이미 존재합니다")
                
        except Exception as e:
            logger.error(f"기본 이슈 확인/생성 실패: {str(e)}")
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            },
            timeout=aiohttp.ClientTimeout(total=10)  # 빠른 타임아웃
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
    
    async def collect_article_links(self) -> List[str]:
        """서울경제 정치 기사 링크를 수집합니다."""
        self.console.print("🔍 서울경제 정치 기사 링크 수집 중...")
        
        all_links = []
        page = 1
        max_pages = 50  # 충분한 페이지 수
        
        while len(all_links) < self.max_articles and page <= max_pages:
            try:
                # 페이지별 URL 구성
                if page == 1:
                    url = self.politics_url
                else:
                    url = f"https://www.sedaily.com/NewsMain/GE/{page}"
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # 1. 고정 기사들 수집 (sub_lv1, sub_news)
                        fixed_articles = soup.select('.sub_lv1 .article_tit a, .sub_news .article_tit a')
                        for article in fixed_articles:
                            href = article.get('href')
                            if href:
                                if href.startswith('/'):
                                    full_url = urljoin(self.base_url, href)
                                else:
                                    full_url = href
                                
                                if full_url not in all_links:
                                    all_links.append(full_url)
                        
                        # 2. 기사 리스트 수집 (sub_news_list)
                        article_list = soup.select('.sub_news_list li .article_tit a')
                        page_count = 0
                        
                        for article in article_list:
                            href = article.get('href')
                            if href:
                                if href.startswith('/'):
                                    full_url = urljoin(self.base_url, href)
                                else:
                                    full_url = href
                                
                                if full_url not in all_links:
                                    all_links.append(full_url)
                                    page_count += 1
                        
                        self.console.print(f"📄 페이지 {page}: {len(fixed_articles)}개 고정 + {page_count}개 리스트 (총 {len(all_links)}개)")
                        
                        if len(all_links) >= self.max_articles:
                            break
                        
                        # 더 이상 새 기사가 없으면 중단
                        if page_count == 0 and page > 1:
                            break
                        
                        page += 1
                        await asyncio.sleep(self.delay)
                        
                    else:
                        self.console.print(f"[red]페이지 {page} 로드 실패: {response.status}[/red]")
                        break
                        
            except Exception as e:
                self.console.print(f"[red]페이지 {page} 처리 실패: {str(e)}[/red]")
                break
        
        # 중복 제거
        unique_links = list(set(all_links))
        self.console.print(f"✅ 총 {len(unique_links)}개 기사 링크 수집 완료")
        
        return unique_links[:self.max_articles]
    
    async def extract_article_content(self, url: str) -> Optional[Dict]:
        """기사 내용을 추출합니다."""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # 제목 추출: 상세 페이지에서는 title 태그나 meta 태그 사용
                    title = None
                    
                    # 1차: meta property="og:title" 에서 제목 추출
                    meta_title = soup.select_one('meta[property="og:title"]')
                    if meta_title:
                        title = meta_title.get('content', '').strip()
                        # '| 서울경제' 제거
                        if title.endswith(' | 서울경제'):
                            title = title[:-6].strip()
                    
                    # 2차: title 태그에서 제목 추출
                    if not title:
                        title_elem = soup.select_one('title')
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                            # '| 서울경제' 제거
                            if title.endswith(' | 서울경제'):
                                title = title[:-6].strip()
                    
                    if not title:
                        if self.debug:
                            self.console.print(f"[yellow]제목 추출 실패 - HTML 구조 확인: {url}[/yellow]")
                            # HTML 구조 일부 출력
                            html_preview = html[:1000] if len(html) > 1000 else html
                            self.console.print(f"[dim]HTML 미리보기: {html_preview}...[/dim]")
                        return None
                    
                    # 발행일 추출: url_txt 클래스 em 태그 뒤의 span 태그
                    published_at = None
                    url_txt_elem = soup.select_one('.url_txt')
                    if url_txt_elem:
                        # em 태그 뒤의 span 태그 찾기
                        em_elem = url_txt_elem.find('em')
                        if em_elem:
                            span_elem = em_elem.find_next_sibling('span')
                            if span_elem:
                                date_text = span_elem.get_text(strip=True)
                                # 날짜 파싱 시도
                                try:
                                    # 다양한 날짜 형식 처리
                                    if re.match(r'\d{4}-\d{2}-\d{2}', date_text):
                                        published_at = datetime.strptime(date_text, '%Y-%m-%d')
                                    elif re.match(r'\d{2}-\d{2}', date_text):
                                        # 현재 연도 추가
                                        current_year = datetime.now().year
                                        date_text = f"{current_year}-{date_text}"
                                        published_at = datetime.strptime(date_text, '%Y-%m-%d')
                                    else:
                                        published_at = datetime.now()
                                except:
                                    published_at = datetime.now()
                    
                    if not published_at:
                        published_at = datetime.now()
                    
                    # 본문 추출: 다양한 선택자 시도
                    content_elems = None
                    
                    # 1차: article_view 클래스 (기본)
                    content_elems = soup.select('.article_view')
                    
                    # 2차: 일반적인 기사 본문 선택자들
                    if not content_elems:
                        content_elems = soup.select('.article_content') or soup.select('.content') or soup.select('.news_content')
                    
                    # 3차: 더 광범위한 본문 선택자들
                    if not content_elems:
                        content_elems = soup.select('.article_body') or soup.select('.news_body') or soup.select('.text')
                    
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
                    
                    # 본문 텍스트 추출 및 정리
                    content_parts = []
                    for elem in content_elems:
                        # <br> 태그를 기준으로 텍스트 분리
                        text = elem.get_text(separator='\n', strip=True)
                        lines = [line.strip() for line in text.split('\n') if line.strip()]
                        content_parts.extend(lines)
                    
                    content = '\n\n'.join(content_parts)
                    
                    if not content.strip():
                        if self.debug:
                            self.console.print(f"[yellow]본문 내용이 비어있음: {url}[/yellow]")
                        return None
                    
                    return {
                        'title': title,
                        'content': content,
                        'url': url,
                        'published_at': published_at
                    }
                    
        except Exception as e:
            if self.debug:
                self.console.print(f"[red]기사 내용 추출 실패 ({url}): {str(e)}[/red]")
            return None
    
    async def save_to_database(self, article_data: Dict) -> bool:
        """기사를 데이터베이스에 저장합니다."""
        try:
            # 서울경제 언론사 정보 가져오기
            # media_outlet = self.supabase_manager.get_media_outlet("서울경제") # 이 부분은 _init_media_outlet에서 처리됨
            # if not media_outlet:
            #     # 서울경제가 없으면 생성 (보수 성향)
            #     media_id = self.supabase_manager.create_media_outlet("서울경제", "right")
            # else:
            #     media_id = media_outlet['id']
            
            # 기사 데이터 구성
            processed_data = {
                'title': article_data['title'],
                'content': article_data['content'],
                'url': article_data['url'],
                'published_at': article_data['published_at'].isoformat(),
                'media_id': self.media_id, # 이 부분은 _init_media_outlet에서 처리됨
                'bias': self.media_bias, # 이 부분은 __init__에서 처리됨
                'issue_id': 1  # 이 부분은 create_default_issue에서 처리됨
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
        self.console.print("🚀 서울경제 정치 기사 크롤러 시작!")
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
            self.console.print("      서울경제 크롤링 결과      ")
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
            self.console.print("✅ 서울경제 크롤링 완료! 🎉")
            
        except Exception as e:
            self.console.print(f"[red]크롤러 실행 실패: {str(e)}[/red]")


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
        
        # 기본 이슈 확인/생성
        await self.create_default_issue()
        
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
    # 디버깅 모드로 실행 (본문 추출 실패 원인 확인)
    async with SedailyPoliticsCrawler(debug=True) as crawler:
        await crawler.run()

if __name__ == "__main__":
    asyncio.run(main())
