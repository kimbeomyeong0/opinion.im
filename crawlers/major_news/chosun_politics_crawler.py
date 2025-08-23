#!/usr/bin/env python3
"""
조선일보 정치 기사 크롤러 (최적화된 버전)
품질 우선: Playwright를 사용한 본문 수집
"""

import asyncio
import json
import re
import httpx
import random
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from rich.console import Console
from rich.table import Table

# 프로젝트 내부 모듈
from utils.supabase_manager_unified import UnifiedSupabaseManager
from utils.common import make_request

console = Console()

class ChosunPoliticsCollector:
    """조선일보 정치 기사 수집기 - 품질 우선"""
    
    def __init__(self):
        self.base_url = "https://www.chosun.com"
        self.politics_url = "https://www.chosun.com/politics/"
        self.media_name = "조선일보"
        self.media_bias = "Right"
        
        # 설정
        self.CONFIG = {
            "target_count": 100,
            "timeout": 10,
            "max_retries": 3,
            "concurrent_limit": 3
        }
        
        # HTTP 헤더
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # 상태 변수
        self.articles = []
        self.today = datetime.now().strftime('%Y-%m-%d')
        
        # 날짜 범위 (최근 7일)
        self.date_range = []
        for i in range(7):
            date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
            self.date_range.append(date)
        
        # Supabase 매니저 초기화
        self.supabase_manager = UnifiedSupabaseManager()
        
        # Playwright 관련
        self._playwright = None
        self._browser = None

    async def _make_request(self, url: str, params: Optional[Dict] = None) -> Optional[str]:
        """HTTP GET 요청 수행"""
        return await make_request(url, "httpx", "GET", params=params, headers=self.headers, timeout=self.CONFIG["timeout"])

    async def _collect_from_html(self):
        """HTML에서 기사 수집"""
        try:
            console.print("📰 HTML에서 기사 데이터 추출 중...")
            html = await self._make_request(self.politics_url)
            if not html:
                console.print("❌ HTML 수집 실패")
                return
            
            # JSON 데이터 추출 시도
            articles = self._extract_json_data_from_html(html)
            
            # JSON에서 추출 실패 시 HTML 직접 파싱
            if not articles:
                articles = self._extract_articles_from_html_direct(html)
            
            # 기사 추가
            for article in articles:
                if self._add_article_to_collection(article):
                    continue
            
            console.print(f"✅ HTML 수집 완료: {len(self.articles)}개 기사 (총 {len(self.articles)}개)")
            
        except Exception as e:
            console.print(f"❌ HTML 수집 오류: {str(e)}")

    def _extract_json_data_from_html(self, html: str) -> List[Dict]:
        """HTML에서 JSON 데이터 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            scripts = soup.find_all('script')
            
            for script in scripts:
                if not script.string:
                    continue
                
                script_text = script.string
                
                if 'content_elements' in script_text and 'headlines' in script_text:
                    try:
                        start_idx = script_text.find('{')
                        end_idx = script_text.rfind('}') + 1
                        
                        if start_idx != -1 and end_idx != -1:
                            json_str = script_text[start_idx:end_idx]
                            data = json.loads(json_str)
                            articles.extend(self._parse_content_elements(data))
                    except (json.JSONDecodeError, Exception) as e:
                        continue
            
            return articles
            
        except Exception as e:
            console.print(f"❌ JSON 추출 오류: {str(e)}")
            return []

    def _extract_articles_from_html_direct(self, html: str) -> List[Dict]:
        """HTML에서 직접 기사 추출"""
        articles = []
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 상단 고정 기사
            flex_chains = soup.find_all('section', class_='flex-chain')
            for chain in flex_chains:
                story_cards = chain.find_all('div', class_='story-card-container')
                for card in story_cards:
                    article = self._extract_single_article(card)
                    if article:
                        articles.append(article)
            
            # 일반 기사 리스트
            feed_items = soup.find_all('div', class_='feed-item')
            for item in feed_items:
                article = self._extract_single_article(item)
                if article:
                    articles.append(article)
            
            return articles
            
        except Exception as e:
            console.print(f"❌ HTML 직접 추출 오류: {str(e)}")
            return []

    def _extract_single_article(self, container) -> Optional[Dict]:
        """개별 기사 추출"""
        try:
            headline = container.find('a', class_='story-card__headline')
            if not headline:
                return None
            
            title = self._clean_title(headline.get_text(strip=True))
            if not title or len(title) < 5:
                return None
            
            url = headline.get('href', '')
            if not url:
                return None
            
            if url.startswith('/'):
                url = urljoin(self.base_url, url)
            
            # 요약 추출
            deck = container.find('div', class_='story-card__deck')
            content = deck.get_text(strip=True) if deck else ""
            
            # 날짜 추출
            datetime_elem = container.find('div', class_='story-card__sigline-datetime')
            date = ""
            if datetime_elem:
                time_text = datetime_elem.find('div', class_='text')
                if time_text:
                    date = self._parse_relative_time(time_text.get_text(strip=True))
            
            if not date:
                date = self.today
            
            # 기자 추출
            author_elem = container.find('span', class_='story-card__sigline-author')
            author = author_elem.get_text(strip=True) if author_elem else ""
            
            # 상단 고정 기사 여부
            is_top = container.find_parent('section', class_='flex-chain') is not None
            
            return {
                'title': title,
                'url': url,
                'content': content,
                'date': date,
                'author': author,
                'is_top': is_top
            }
            
        except Exception as e:
            return None

    async def _collect_from_api(self):
        """API를 통한 추가 기사 수집"""
        try:
            console.print("🔌 API를 통한 기사 수집 시작...")
            
            api_base = "https://www.chosun.com/pf/api/v3/content/fetch/story-feed"
            offset = 20
            size = 50
            
            while len(self.articles) < self.CONFIG["target_count"] and offset < 2000:
                try:
                    query_params = {
                        "query": json.dumps({
                            "excludeContentTypes": "gallery, video",
                            "includeContentTypes": "story",
                            "includeSections": "/politics",
                            "offset": offset,
                            "size": size
                        }),
                        "filter": "{content_elements{_id,canonical_url,credits{by{_id,additional_properties{original{affiliations,byline}},name,org,url}},description{basic},display_date,headlines{basic,mobile},label{membership_icon{text}},last_updated_date,promo_items{basic{_id,additional_properties{focal_point{max,min}},alt_text,caption,content,content_elements{_id,alignment,alt_text,caption,content,credits{affiliation{name},by{_id,byline,name,org}},height,resizedUrls{16x9_lg,16x9_md,16x9_sm,16x9_xxl,4x3_lg,4x3_md,4x3_sm,4x3_xxl},subtype,type,url,width},credits{affiliation{byline,name},by{byline,name}},description{basic},embed_html,focal_point{x,y},headlines{basic},height,promo_items{basic{_id,height,resizedUrls{16x9_lg,16x9_md,16x9_sm,16x9_xxl,4x3_lg,4x3_md,4x3_sm,4x3_xxl},subtype,type,url,width}},resizedUrls{16x9_lg,16x9_md,16x9_sm,16x9_xxl,4x3_lg,4x3_md,4x3_sm,4x3_xxl},streams{height,width},subtype,type,url,websites,width},lead_art{duration,type}},related_content{basic{_id,absolute_canonical_url,headlines{basic,mobile},referent{id,type},type}},subtype,taxonomy{primary_section{_id,name},tags{slug,text}},type,website_url},count,next}",
                        "d": "1912",
                        "mxId": "00000000",
                        "_website": "chosun"
                    }
                    
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(api_base, params=query_params)
                        response.raise_for_status()
                        data = response.json()
                        
                        content_elements = data.get('content_elements', [])
                        if not content_elements:
                            break
                        
                        new_articles = 0
                        for element in content_elements:
                            if len(self.articles) >= self.CONFIG["target_count"]:
                                break
                            
                            article = self._parse_api_article(element)
                            if article and self._add_article_to_collection(article):
                                new_articles += 1
                        
                        console.print(f"✅ API 호출 (offset: {offset}): {new_articles}개 기사 추가 (총 {len(self.articles)}개)")
                        
                        if new_articles == 0:
                            break
                        
                        offset += size
                        await asyncio.sleep(0.05)
                        
                except Exception as e:
                    console.print(f"❌ API 호출 오류 (offset: {offset}): {str(e)}")
                    offset += size
                    continue
            
            console.print(f"🎯 API 수집 완료: 총 {len(self.articles)}개 기사")
            
        except Exception as e:
            console.print(f"❌ API 수집 전체 오류: {str(e)}")

    def _parse_api_article(self, element: Dict) -> Optional[Dict]:
        """API 응답의 기사 요소를 파싱"""
        try:
            headlines = element.get('headlines', {})
            title = headlines.get('basic', '')
            if not title or len(title) < 5:
                return None
            
            canonical_url = element.get('canonical_url', '')
            if not canonical_url:
                return None
            
            if canonical_url.startswith('/'):
                url = urljoin(self.base_url, canonical_url)
            else:
                url = canonical_url
            
            description = element.get('description', {})
            content = description.get('basic', '')
            
            display_date = element.get('display_date', '')
            date = self._parse_date(display_date)
            if not date:
                date = self.today
            
            credits = element.get('credits', {})
            by_list = credits.get('by', [])
            author = ""
            if by_list and len(by_list) > 0:
                by_info = by_list[0]
                additional_props = by_info.get('additional_properties', {})
                original = additional_props.get('original', {})
                author = original.get('byline', '')
                if not author:
                    author = by_info.get('name', '')
            
            return {
                'title': title,
                'url': url,
                'content': content,
                'date': date,
                'author': author,
                'source': 'api'
            }
            
        except Exception as e:
            return None

    async def _collect_article_contents(self, articles: List[Dict]):
        """기사 본문 수집 (품질 우선)"""
        if not articles:
            return
        
        console.print(f"📖 {len(articles)}개 기사 본문 수집 중...")
        
        semaphore = asyncio.Semaphore(self.CONFIG["concurrent_limit"])
        
        async def process_article(article):
            async with semaphore:
                try:
                    url = article['url']
                    
                    # Playwright로 본문 추출
                    content = await self._extract_content_with_playwright(url)
                    
                    if content and len(content.strip()) > 50:
                        article['content'] = content
                        return True
                    else:
                        # HTML 파싱으로 대체
                        content = await self._extract_content_from_html(url)
                        if content and len(content.strip()) > 50:
                            article['content'] = content
                            return True
                    
                    return False
                    
                except Exception as e:
                    console.print(f"⚠️ 본문 추출 실패 ({article.get('title', 'Unknown')}): {str(e)}")
                    return False
        
        tasks = [process_article(article) for article in articles]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        success_count = sum(1 for r in results if r is True)
        console.print(f"✅ 본문 수집 완료: {success_count}/{len(articles)}개 성공")

    async def _extract_content_with_playwright(self, url: str) -> str:
        """Playwright를 활용하여 본문 추출"""
        try:
            from playwright.async_api import async_playwright
            
            if not hasattr(self, '_browser'):
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=True,
                    args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
                )
            
            page = await self._browser.new_page()
            
            try:
                await page.goto(url, wait_until='domcontentloaded', timeout=10000)
                await page.wait_for_timeout(1000)
                
                try:
                    await page.wait_for_selector('section.article-body', timeout=5000)
                except:
                    selectors = [
                        'section[itemprop="articleBody"]',
                        'article.article-body',
                        'div.article-body',
                        'div#article-body'
                    ]
                    
                    for selector in selectors:
                        try:
                            await page.wait_for_selector(selector, timeout=4000)
                            break
                        except:
                            continue
                
                content = await page.evaluate('''() => {
                    let paragraphs = document.querySelectorAll('p.article-body__content.article-body__content-text');
                    
                    if (paragraphs.length === 0) {
                        paragraphs = document.querySelectorAll('p.article-body__content');
                    }
                    
                    if (paragraphs.length === 0) {
                        const articleBody = document.querySelector('section.article-body');
                        if (articleBody) {
                            paragraphs = articleBody.querySelectorAll('p');
                        }
                    }
                    
                    if (paragraphs.length === 0) {
                        paragraphs = document.querySelectorAll('article p, .content p, .article p');
                    }
                    
                    const textContent = Array.from(paragraphs)
                        .map(p => p.textContent.trim())
                        .filter(text => text.length > 10)
                        .join('\\n\\n');
                    
                    return textContent;
                }''')
                
                if content and len(content.strip()) > 50:
                    return content.strip()
                
                return ""
                
            finally:
                await page.close()
                
        except Exception as e:
            return ""

    async def _extract_content_from_html(self, url: str) -> str:
        """HTML에서 본문 추출 (백업 방법)"""
        try:
            html = await self._make_request(url)
            if not html:
                return ""
            
            soup = BeautifulSoup(html, 'html.parser')
            
            content_elem = (
                soup.find('section', class_='article-body') or
                soup.find('section', {'itemprop': 'articleBody'}) or
                soup.find('article', class_='article-body') or
                soup.find('div', class_='article-body')
            )
            
            if content_elem:
                p_tags = content_elem.find_all('p', class_='article-body__content')
                
                if not p_tags:
                    p_tags = content_elem.find_all('p')
                
                if p_tags:
                    content = '\n'.join(p.get_text(strip=True) for p in p_tags if p.get_text(strip=True))
                    content = re.sub(r'\n\s*\n', '\n\n', content)
                    return content.strip()
            
            return ""
            
        except Exception as e:
            return ""

    def _add_article_to_collection(self, article: Dict) -> bool:
        """기사를 컬렉션에 추가 (중복 체크)"""
        if not article or not article.get('title') or not article.get('url'):
            return False
        
        # 중복 체크
        for existing in self.articles:
            if existing['url'] == article['url']:
                return False
        
        self.articles.append(article)
        return True

    def _clean_title(self, title: str) -> str:
        """제목 정리"""
        if not title:
            return ""
        
        title = re.sub(r'\s+', ' ', title.strip())
        title = re.sub(r'^[^\w가-힣]+', '', title)
        title = re.sub(r'[^\w가-힣]+$', '', title)
        
        return title

    def _parse_relative_time(self, time_str: str) -> str:
        """상대 시간을 절대 시간으로 변환"""
        try:
            now = datetime.now()
            
            if '분 전' in time_str:
                minutes = int(re.search(r'(\d+)분 전', time_str).group(1))
                target_time = now - timedelta(minutes=minutes)
            elif '시간 전' in time_str:
                hours = int(re.search(r'(\d+)시간 전', time_str).group(1))
                target_time = now - timedelta(hours=hours)
            elif '일 전' in time_str or '일전' in time_str:
                days = int(re.search(r'(\d+)일', time_str).group(1))
                target_time = now - timedelta(days=days)
            else:
                return self.today
            
            return target_time.strftime('%Y-%m-%d')
            
        except:
            return self.today

    def _parse_date(self, date_str: str) -> str:
        """날짜 문자열 파싱"""
        try:
            if not date_str:
                return self.today
            
            # ISO 형식
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                return dt.strftime('%Y-%m-%d')
            
            return self.today
            
        except:
            return self.today

    def _parse_content_elements(self, data: Dict) -> List[Dict]:
        """JSON 데이터에서 content_elements 파싱"""
        articles = []
        
        try:
            content_elements = data.get('content_elements', [])
            
            for element in content_elements:
                article = self._parse_api_article(element)
                if article:
                    articles.append(article)
            
            return articles
            
        except Exception as e:
            return []

    async def _cleanup_playwright(self):
        """Playwright 리소스 정리"""
        try:
            if hasattr(self, '_browser') and self._browser:
                await self._browser.close()
            
            if hasattr(self, '_playwright') and self._playwright:
                await self._playwright.stop()
                
        except Exception as e:
            console.print(f"⚠️ Playwright 정리 오류: {str(e)}")

    async def collect_all_articles(self) -> List[Dict]:
        """모든 기사 수집 (메인 메서드)"""
        start_time = datetime.now()
        
        console.print("🚀 조선일보 정치 기사 크롤링 시작 (품질 우선)")
        console.print(f"📅 대상 날짜 범위: {self.date_range}")
        console.print(f"🎯 목표: {self.CONFIG['target_count']}개 기사")
        console.print(f"⏱️ 목표 시간: 품질 우선 (본문 수집)")
        console.print("=" * 50)
        
        try:
            # 1차: HTML에서 기사 수집
            await self._collect_from_html()
            
            # 2차: API를 통한 추가 기사 수집
            if len(self.articles) < self.CONFIG["target_count"]:
                console.print("📰 API를 통한 추가 기사 수집 중...")
                await self._collect_from_api()
            
            # 결과 제한
            if len(self.articles) > self.CONFIG["target_count"]:
                self.articles = self.articles[:self.CONFIG["target_count"]]
            
            # 품질 검증: 제목이 너무 짧은 기사 제외
            self.articles = [article for article in self.articles if len(article['title'].strip()) >= 5]
            
            # 기사 본문 수집 (품질 우선)
            console.print(f"📖 기사 본문 수집 시작... (품질 우선)")
            await self._collect_article_contents(self.articles)
            
            # 품질 검증: 본문이 없는 기사 제외
            self.articles = [article for article in self.articles if article.get('content', '').strip()]
            console.print(f"✅ 본문 수집 완료: {len(self.articles)}개 기사 (본문 있음)")
            
            # Playwright 리소스 정리
            await self._cleanup_playwright()
            
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
            
            if elapsed <= 120:  # 품질 우선이므로 2분 목표
                console.print("✅ 목표 시간 달성! (2분 이내)")
            else:
                console.print("⏰ 목표 시간 초과")
            
            return self.articles
            
        except Exception as e:
            console.print(f"❌ 크롤링 오류: {str(e)}")
            await self._cleanup_playwright()
            return []

    def display_results(self, articles: List[Dict]):
        """수집 결과 표시"""
        if not articles:
            console.print("❌ 수집된 기사가 없습니다.")
            return
        
        console.print(f"\n📰 수집된 기사 예시:")
        
        table = Table(title="수집된 기사 목록")
        table.add_column("번호", justify="right", style="cyan", no_wrap=True)
        table.add_column("제목", style="magenta", max_width=50)
        table.add_column("날짜", justify="center", style="green")
        table.add_column("URL", style="blue", max_width=50)
        
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
        
        # 미디어 아울렛 정보 조회
        media_outlet = self.supabase_manager.get_media_outlet('조선일보')
        if not media_outlet:
            console.print("❌ 조선일보 미디어 아울렛 정보를 찾을 수 없습니다.")
            return {"success": 0, "failed": len(articles)}
        
        # 임의의 이슈 ID 가져오기
        issue_id = self.supabase_manager.get_random_issue_id()
        if not issue_id:
            console.print("❌ 이슈 ID를 가져올 수 없습니다.")
            return {"success": 0, "failed": len(articles)}
        
        console.print(f"✅ 미디어: {media_outlet['name']} (ID: {media_outlet['id']})")
        console.print(f"✅ 이슈 ID: {issue_id}")
        
        # 기사 저장
        success_count = 0
        failed_count = 0
        
        for i, article in enumerate(articles, 1):
            try:
                article_data = {
                    "title": article["title"],
                    "url": article["url"],
                    "content": article.get("content", ""),
                    "published_at": article["date"],
                    "media_id": media_outlet["id"],
                    "issue_id": issue_id,
                    "bias": media_outlet.get("bias", self.media_bias)
                }
                
                if self.supabase_manager.insert_article(article_data):
                    success_count += 1
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
        console.print(f"   - 성공률: {(success_count / len(articles) * 100):.1f}%")
        
        return {"success": success_count, "failed": failed_count}

    async def run(self):
        """크롤러 실행"""
        try:
            # 기사 수집
            articles = await self.collect_all_articles()
            
            if not articles:
                console.print("❌ 수집된 기사가 없습니다.")
                return
            
            # 결과 표시
            self.display_results(articles)
            
            # Supabase에 저장
            save_result = await self.save_to_supabase(articles)
            
            # 최종 결과
            total_time = datetime.now().strftime('%H:%M:%S')
            console.print(f"\n🎯 최종 결과: [성공 {len(articles)}개 / 실패 {save_result['failed']}개 / 총 소요시간 {total_time}]")
            
        except Exception as e:
            console.print(f"❌ 실행 오류: {str(e)}")
            traceback.print_exc()


async def main():
    """메인 함수"""
    collector = ChosunPoliticsCollector()
    await collector.run()


if __name__ == "__main__":
    asyncio.run(main())

