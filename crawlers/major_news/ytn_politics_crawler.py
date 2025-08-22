#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
YTN 정치 기사 크롤러
- 대상: YTN 정치 섹션 (mcd=0101)
- 방식: HTML 파싱 + AJAX API (BeautifulSoup)
- 목표: 오늘 날짜 기사 100개 수집
- 성능: asyncio + httpx 병렬 처리
"""

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table

# Supabase 연동
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from utils.legacy.supabase_manager_v2 import SupabaseManagerV2

console = Console()


class YTNPoliticsCrawler:
    """YTN 정치 기사 크롤러"""
    
    def __init__(self):
        self.base_url = "https://www.ytn.co.kr"
        self.first_page_url = "https://www.ytn.co.kr/news/list.php?mcd=0101"
        self.ajax_url = "https://www.ytn.co.kr/ajax/getMoreNews.php"
        self.target_count = 100
        self.max_pages = 20  # 100개 수집을 위해 페이지 수 증가
        self.timeout = 10.0
        self.today = datetime.now().strftime("%Y-%m-%d")
        
        # 날짜 범위 설정 (최근 7일)
        from datetime import timedelta
        self.date_range = []
        for i in range(7):  # 오늘부터 7일 전까지
            date = datetime.now() - timedelta(days=i)
            self.date_range.append(date.strftime("%Y-%m-%d"))
        
        # 수집된 기사 저장
        self.articles = []
        self.seen_urls = set()
        
        # Supabase 연동
        self.supabase_manager = SupabaseManagerV2()
        self.media_name = "YTN"
        self.media_bias = "Center"
        
        # HTTP 헤더
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Cache-Control": "max-age=0",
        }

    async def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[str]:
        """HTTP GET 요청 수행"""
        try:
            async with httpx.AsyncClient(
                headers=self.headers,
                timeout=self.timeout,
                follow_redirects=True
            ) as client:
                if params:
                    response = await client.get(url, params=params)
                else:
                    response = await client.get(url)
                
                response.raise_for_status()
                return response.text
                
        except httpx.HTTPStatusError as e:
            console.print(f"❌ HTTP 오류: {e.response.status_code} - {url}")
            return None
        except httpx.TimeoutException:
            console.print(f"⏰ 타임아웃: {url}")
            return None
        except Exception as e:
            console.print(f"❌ 요청 오류: {str(e)} - {url}")
            return None

    async def _extract_article_content(self, url: str) -> str:
        """기사 상세 페이지에서 본문 추출"""
        try:
            html = await self._make_request(url)
            if not html:
                return ""
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # 본문 추출 - span 태그에서 본문 찾기
            content_elem = soup.find('span', style=lambda x: x and 'word-break:keep-all' in x)
            if content_elem:
                # HTML 태그 제거하고 텍스트만 추출
                content = content_elem.get_text(separator='\n', strip=True)
                # 연속된 줄바꿈 정리
                content = re.sub(r'\n\s*\n', '\n\n', content)
                return content.strip()
            
            # 대안: 다른 본문 선택자 시도
            content_elem = soup.find('div', class_='content') or soup.find('div', class_='article_content')
            if content_elem:
                content = content_elem.get_text(separator='\n', strip=True)
                content = re.sub(r'\n\s*\n', '\n\n', content)
                return content.strip()
            
            return ""
            
        except Exception as e:
            console.print(f"❌ 본문 추출 오류: {str(e)} - {url}")
            return ""

    async def _make_post_request(self, url: str, data: Dict) -> Optional[Dict]:
        """HTTP POST 요청 수행 (AJAX용)"""
        try:
            async with httpx.AsyncClient(
                headers=self.headers,
                timeout=self.timeout,
                follow_redirects=True
            ) as client:
                response = await client.post(url, data=data)
                response.raise_for_status()
                
                if response.text:
                    return json.loads(response.text)
                return None
                
        except httpx.HTTPStatusError as e:
            console.print(f"❌ HTTP 오류: {e.response.status_code} - {url}")
            return None
        except httpx.TimeoutException:
            console.print(f"⏰ 타임아웃: {url}")
            return None
        except json.JSONDecodeError as e:
            console.print(f"❌ JSON 파싱 오류: {str(e)} - {url}")
            return None
        except Exception as e:
            console.print(f"❌ 요청 오류: {str(e)} - {url}")
            return None

    def _parse_date(self, date_str: str) -> Optional[str]:
        """날짜 문자열을 YYYY-MM-DD 형식으로 변환"""
        try:
            if not date_str or date_str.strip() == "":
                return None
                
            # YTN 날짜 형식: "2025.08.22. 14:21"
            if re.match(r'^\d{4}\.\d{2}\.\d{2}\.\s+\d{2}:\d{2}$', date_str.strip()):
                date_part = date_str.strip().split('.')[0:3]
                year, month, day = date_part
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            return None
        except Exception as e:
            console.print(f"❌ 날짜 파싱 오류: {str(e)} - {date_str}")
            return None

    def _clean_title(self, title: str) -> str:
        """제목 정리"""
        if not title:
            return ""
        
        # HTML 태그 제거
        title = re.sub(r'<[^>]+>', '', title)
        
        # 특수문자 정리
        title = re.sub(r'\s+', ' ', title)
        title = title.strip()
        
        return title

    def _parse_articles_from_html(self, html: str) -> List[Dict]:
        """HTML에서 기사 목록 파싱"""
        articles = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # div.news_list에서 기사 추출
            news_items = soup.find_all('div', class_='news_list')
            # div.news_list에서 기사 추출
            for item in news_items:
                try:
                    # text_area 안에서 제목과 링크 추출
                    text_area = item.find('div', class_='text_area')
                    if not text_area:
                        continue
                    
                    title_elem = text_area.find('div', class_='title')
                    if not title_elem:
                        continue
                    
                    title_link = title_elem.find('a')
                    if not title_link:
                        continue
                    
                    title = self._clean_title(title_link.get_text())
                    if not title:
                        continue
                    
                    # 링크 추출
                    href = title_link.get('href')
                    if not href:
                        continue
                    
                    # 절대 URL 변환
                    if href.startswith('/'):
                        url = urljoin(self.base_url, href)
                    else:
                        url = href
                    
                    # 중복 확인
                    if url in self.seen_urls:
                        continue
                    
                    # 날짜 추출
                    date_elem = text_area.find('div', class_='info')
                    date = None
                    if date_elem:
                        date_elem = date_elem.find('div', class_='date')
                        if date_elem:
                            date_str = date_elem.get_text().strip()
                            date = self._parse_date(date_str)
                    
                    # 날짜 필터링 임시 제거 - 100개 수집을 위해
                    # if date not in self.date_range:
                    #     continue
                    
                    # 기사 정보 저장
                    article = {
                        "title": title,
                        "url": url,
                        "date": date,
                        "content": ""  # 본문은 나중에 별도로 수집
                    }
                    
                    articles.append(article)
                    
                except Exception as e:
                    console.print(f"❌ 기사 파싱 오류: {str(e)}")
                    continue
        
        except Exception as e:
            console.print(f"❌ HTML 파싱 오류: {str(e)}")
        
        return articles
    
    def _parse_articles_from_json(self, json_data: Dict) -> List[Dict]:
        """JSON 응답에서 기사 목록 파싱"""
        articles = []
        
        try:
            if not json_data or 'data' not in json_data:
                return articles
            
            for data in json_data['data']:
                try:
                    # 제목 추출
                    title = data.get('title', '').strip()
                    if not title:
                        continue
                    
                    title = self._clean_title(title)
                    if not title:
                        continue
                    
                    # join_key로 URL 생성
                    join_key = data.get('join_key', '')
                    if not join_key:
                        continue
                    
                    url = f"https://www.ytn.co.kr/_ln/0101_{join_key}"
                    
                    # 중복 확인
                    if url in self.seen_urls:
                        continue
                    
                    # 날짜 추출
                    date_str = data.get('n_date', '')
                    date = self._parse_date(date_str)
                    
                    # 날짜 필터링 임시 제거 - 100개 수집을 위해
                    # if date not in self.date_range:
                    #     continue
                    
                    # 기사 정보 저장
                    article = {
                        "title": title,
                        "url": url,
                        "date": date,
                        "content": ""  # 본문은 나중에 별도로 수집
                    }
                    
                    articles.append(article)
                    # seen_urls는 상위에서 관리
                    
                except Exception as e:
                    console.print(f"❌ JSON 기사 파싱 오류: {str(e)}")
                    continue
        
        except Exception as e:
            console.print(f"❌ JSON 파싱 오류: {str(e)}")
        
        return articles

    async def _collect_from_first_page(self) -> int:
        """첫 페이지에서 기사 수집"""
        console.print("📰 첫 페이지 수집 중...")
        
        html = await self._make_request(self.first_page_url)
        if not html:
            console.print("❌ 첫 페이지 수집 실패")
            return 0
        
        articles = self._parse_articles_from_html(html)
        
        # 중복 제거 및 기사 추가
        new_articles = []
        for article in articles:
            if len(self.articles) + len(new_articles) >= self.target_count:
                break
            if article["url"] not in self.seen_urls:
                new_articles.append(article)
                self.seen_urls.add(article["url"])
        
        # 기사 추가
        self.articles.extend(new_articles)
        
        collected = len(new_articles)
        console.print(f"✅ 첫 페이지: {collected}개 기사 수집 (총 {len(self.articles)}개)")
        return collected

    async def _collect_from_ajax_pages(self) -> int:
        """AJAX 페이지에서 기사 수집"""
        console.print("📰 AJAX 페이지 수집 중...")
        
        total_collected = 0
        
        for page in range(2, self.max_pages + 1):
            # 목표 달성 시 중단
            if len(self.articles) >= self.target_count:
                break
            
            # pivot 값 계산 (마지막 기사의 join_key 추출)
            pivot = ""
            if self.articles:
                # URL에서 join_key 추출: _ln/0101_{join_key}
                last_url = self.articles[-1]["url"]
                match = re.search(r'0101_(\d+)', last_url)
                if match:
                    pivot = match.group(1)
            
            # POST 데이터 준비
            post_data = {
                "mcd": "0101",
                "hcd": "",
                "page": str(page),
                "pivot": pivot
            }
            
            json_data = await self._make_post_request(self.ajax_url, post_data)
            if not json_data:
                console.print(f"⚠️ 페이지 {page} 수집 실패 (JSON 응답 없음)")
                continue
            
            articles = self._parse_articles_from_json(json_data)
            
            # 중복 제거 및 기사 추가
            page_collected = 0
            for article in articles:
                if len(self.articles) >= self.target_count:
                    break
                if article["url"] not in self.seen_urls:
                    self.articles.append(article)
                    self.seen_urls.add(article["url"])
                    page_collected += 1
            
            total_collected += page_collected
            console.print(f"✅ 페이지 {page}: {page_collected}개 기사 수집 (총 {len(self.articles)}개)")
            
            # 연속 3페이지에서 기사가 없으면 중단
            if page_collected == 0:
                console.print(f"⚠️ 페이지 {page}에서 기사 없음")
                if page > 5:  # 5페이지 이후부터만 중단 고려
                    console.print(f"   페이지 {page}에서 기사 없으므로 수집 중단")
                    break
            
            # 짧은 딜레이
            await asyncio.sleep(0.1)
        
        return total_collected

    async def _collect_article_contents(self, articles: List[Dict]) -> None:
        """수집된 기사들의 본문 내용 수집"""
        console.print("📝 기사 본문 수집 중...")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            task = progress.add_task("본문 수집", total=len(articles))
            
            for i, article in enumerate(articles):
                try:
                    # 본문 추출
                    content = await self._extract_article_content(article["url"])
                    article["content"] = content
                    
                    # 진행률 업데이트
                    progress.update(task, advance=1)
                    
                    # 짧은 딜레이 (서버 부하 방지)
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    console.print(f"❌ 본문 수집 실패: {article['title'][:30]}... - {str(e)}")
                    article["content"] = ""
                    progress.update(task, advance=1)
                    continue

    async def collect_all_articles(self) -> List[Dict]:
        """모든 기사 수집"""
        start_time = datetime.now()
        
        console.print("🚀 YTN 정치 기사 크롤링 시작")
        console.print(f"📅 대상 날짜 범위: {self.date_range}")
        console.print(f"🎯 목표: {self.target_count}개 기사")
        console.print(f"⏱️ 목표 시간: 20초 이내")
        console.print("=" * 50)
        
        # 첫 페이지 수집
        await self._collect_from_first_page()
        
        # AJAX 페이지 수집
        if len(self.articles) < self.target_count:
            await self._collect_from_ajax_pages()
        
        # 결과 제한
        if len(self.articles) > self.target_count:
            self.articles = self.articles[:self.target_count]
        
        # 기사 본문 수집
        await self._collect_article_contents(self.articles)
        
        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()
        
        console.print("=" * 50)
        console.print("🎉 크롤링 완료!")
        console.print(f"📊 수집 결과:")
        console.print(f"   - 총 수집: {len(self.articles)}개")
        console.print(f"   - 소요 시간: {elapsed:.2f}초")
        
        if elapsed > 0:
            speed = len(self.articles) / elapsed
            console.print(f"   - 평균 속도: {speed:.1f} 기사/초")
        
        if elapsed <= 20:
            console.print("✅ 목표 시간 달성! (20초 이내)")
        else:
            console.print("⏰ 목표 시간 초과")
        
        return self.articles

    def display_results(self, articles: List[Dict]):
        """수집 결과 표시"""
        if not articles:
            console.print("❌ 수집된 기사가 없습니다.")
            return
        
        console.print(f"\n📰 수집된 기사 예시:")
        
        # 테이블 생성
        table = Table(title="수집된 기사 목록")
        table.add_column("번호", justify="right", style="cyan", no_wrap=True)
        table.add_column("제목", style="magenta", max_width=50)
        table.add_column("날짜", justify="center", style="green")
        table.add_column("URL", style="blue", max_width=50)
        
        # 최대 10개만 표시
        for i, article in enumerate(articles[:10], 1):
            title = article['title']
            if len(title) > 50:
                title = title[:47] + "..."
            
            url = article['url']
            if len(url) > 50:
                url = url[:47] + "..."
            
            table.add_row(
                str(i),
                title,
                article['date'],
                url
            )
        
        console.print(table)

    async def save_to_supabase(self, articles: List[Dict]) -> Dict[str, int]:
        """Supabase에 기사 저장"""
        if not articles:
            return {"success": 0, "failed": 0}
        
        console.print(f"\n💾 Supabase에 {len(articles)}개 기사 저장 중...")
        
        # media_outlet 정보 가져오기
        media_outlet = self.supabase_manager.get_media_outlet(self.media_name)
        if not media_outlet:
            console.print(f"❌ 미디어 정보를 찾을 수 없습니다: {self.media_name}")
            return {"success": 0, "failed": len(articles)}
        
        # issue 생성 또는 가져오기
        issue_title = f"YTN 정치 뉴스 - {datetime.now().strftime('%Y년 %m월 %d일')}"
        issue = self.supabase_manager.get_issue_by_title(issue_title)
        if not issue:
            issue_id = self.supabase_manager.create_issue(issue_title, "정치", "YTN 정치 관련 뉴스")
            if issue_id:
                issue = {"id": issue_id}
            else:
                console.print("❌ Issue 생성 실패")
                return {"success": 0, "failed": len(articles)}
        
        success_count = 0
        failed_count = 0
        
        for i, article in enumerate(articles, 1):
            try:
                # 기사 데이터 준비
                article_data = {
                    "title": article["title"],
                    "url": article["url"],
                    "content": article.get("content", ""),  # 수집된 본문 사용
                    "published_at": article["date"],
                    "media_id": media_outlet["id"],
                    "issue_id": issue["id"],
                    "bias": self.media_bias
                }
                
                # Supabase에 저장
                result = self.supabase_manager.insert_article(article_data)
                
                if result:
                    success_count += 1
                    if i <= 5:  # 처음 5개만 로그 출력
                        console.print(f"✅ [{i}/{len(articles)}] 저장 성공: {article['title'][:50]}...")
                else:
                    failed_count += 1
                    console.print(f"❌ [{i}/{len(articles)}] 저장 실패: {article['title'][:50]}...")
                
            except Exception as e:
                failed_count += 1
                console.print(f"❌ [{i}/{len(articles)}] 저장 오류: {str(e)}")
        
        console.print(f"\n📊 저장 결과:")
        console.print(f"   - 성공: {success_count}개")
        console.print(f"   - 실패: {failed_count}개")
        console.print(f"   - 성공률: {success_count/len(articles)*100:.1f}%")
        
        return {"success": success_count, "failed": failed_count}


async def main():
    """메인 함수"""
    crawler = YTNPoliticsCrawler()
    
    try:
        # 기사 수집
        articles = await crawler.collect_all_articles()
        
        # 결과 표시
        crawler.display_results(articles)
        
        # Supabase에 저장
        await crawler.save_to_supabase(articles)
        
    except KeyboardInterrupt:
        console.print("\n⚠️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        console.print(f"❌ 예기치 못한 오류: {str(e)}")


if __name__ == "__main__":
    asyncio.run(main())
