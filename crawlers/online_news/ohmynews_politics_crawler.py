from typing import List, Dict
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
오마이뉴스 정치 섹션 크롤러
- 20초 내에 100개 기사 수집
- 본문을 깔끔하게 추출 (군더더기 제거)
- bias를 올바르게 설정 (Left)
"""

import asyncio
import aiohttp
import time
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import sys
import os

# 모듈 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.supabase_manager_unified import UnifiedSupabaseManager
from utils.common.html_parser import HTMLParserUtils

class OhMyNewsPoliticsCrawler:
    def __init__(self):
        self.base_url = "https://www.ohmynews.com/NWS_Web/ArticlePage/Total_Article.aspx"
        self.politics_url = f"{self.base_url}?PAGE_CD=C0400"
        self.manager = UnifiedSupabaseManager()
        
        # 미디어 정보 설정
        self.media_name = "오마이뉴스"
        self.media_bias = "Left"  # 오마이뉴스는 좌편향 성향
        self.media_id = None  # media_outlets에서 가져올 예정
        
        # 기본 설정
        self.issue_id = 1  # 기본 issue_id
        self.collected_articles = set()
        
        # media_outlets에서 오마이뉴스 정보 가져오기
        self._init_media_outlet()
        
    def _init_media_outlet(self):
        """media_outlets에서 오마이뉴스 정보를 초기화합니다."""
        try:
            media_outlet = self.manager.get_media_outlet(self.media_name)
            if media_outlet:
                self.media_id = media_outlet['id']
                print(f"✅ 오마이뉴스 media_id: {self.media_id}, bias: {self.media_bias}")
            else:
                # 오마이뉴스가 없으면 생성
                self.media_id = self.manager.create_media_outlet(self.media_name, self.media_bias)
                print(f"✅ 오마이뉴스 생성됨 - media_id: {self.media_id}, bias: {self.media_bias}")
        except Exception as e:
            print(f"오마이뉴스 media_outlet 초기화 실패: {str(e)}")
            self.media_id = 9  # 기본값 사용
    
    async def create_default_issue(self):
        """기본 이슈가 존재하는지 확인하고 없으면 생성합니다."""
        try:
            # issues 테이블에서 id=1이 존재하는지 확인
            result = self.manager.client.table('issues').select('id').eq('id', 1).execute()
            
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
                
                self.manager.client.table('issues').insert(issue_data).execute()
                print("기본 이슈가 생성되었습니다")
            else:
                print("기본 이슈가 이미 존재합니다")
                
        except Exception as e:
            print(f"기본 이슈 확인/생성 실패: {str(e)}")
    
    async def get_media_outlet(self):
        """미디어 아울렛 정보를 가져옵니다."""
        try:
            result = self.manager.client.table('media_outlets').select('*').eq('id', self.media_id).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            print(f"❌ 미디어 아울렛 정보 가져오기 실패: {e}")
            return None
    
    def collect_article_links(self, html_content):
        """HTML에서 기사 링크를 수집합니다."""
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []
        
        # 기사 목록에서 링크 추출
        articles = soup.find_all('li')
        for article in articles:
            link_elem = article.find('a', href=True)
            if link_elem:
                href = link_elem['href']
                if '/NWS_Web/View/at_pg.aspx?CNTN_CD=' in href:
                    full_url = urljoin('https://www.ohmynews.com', href)
                    if full_url not in self.collected_articles:
                        links.append(full_url)
                        self.collected_articles.add(full_url)
        
        return links
    
    async def fetch_page(self, session, url):
        """페이지를 가져옵니다."""
        try:
            async with session.get(url, timeout=10) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    print(f"⚠️  페이지 가져오기 실패: {url}, 상태: {response.status}")
                    return None
        except Exception as e:
            print(f"❌ 페이지 가져오기 오류: {url}, 오류: {e}")
            return None
    
    def extract_article_content(self, html_content):
        """기사 본문을 추출하고 정리합니다."""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 제목 추출 - 오마이뉴스는 h2.article_tit에 실제 제목이 있음
        title = ""
        title_elem = soup.find('h2', class_='article_tit')
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # 본문 추출 - 오마이뉴스는 div.at_contents에 실제 본문이 있음
        content = ""
        content_elem = soup.select_one('div.at_contents')
        if content_elem:
            content = content_elem.get_text(strip=True)
        
        # 본문이 없으면 다른 방법으로 시도
        if not content:
            content_elem = soup.select_one('div.content_lt')
            if content_elem:
                content = content_elem.get_text(strip=True)
        
        # 본문이 여전히 없으면 다른 방법으로 시도
        if not content:
            content_elem = soup.find('div', class_=re.compile(r'content|body|text|article'))
            if content_elem:
                content = content_elem.get_text(strip=True)
        
        # 날짜 추출 - 공통 유틸리티 사용
        publish_date = HTMLParserUtils.parse_date(html_content)
        
        # 불필요한 요소들 제거 - 오마이뉴스 특화
        unwanted_patterns = [
            r'오마이뉴스.*?',
            r'사이트 전체보기.*?',
            r'인기기사.*?',
            r'topHistory.*?',
            r'이용가이드.*?',
            r'모바일 이용안내.*?',
            r'뉴스.*?',
            r'전체기사.*?',
            r'정치.*?',
            r'경제.*?',
            r'사회.*?',
            r'교육.*?',
            r'미디어.*?',
            r'민족·국제.*?',
            r'여성.*?',
            r'만평·만화.*?',
            r'그래픽뉴스.*?',
            r'카드뉴스.*?',
            r'영상뉴스.*?',
            r'사는이야기.*?',
            r'문화.*?',
            r'여행.*?',
            r'책.*?',
            r'동네뉴스.*?',
            r'지도.*?',
            r'지역.*?',
            r'제휴매체.*?',
            r'시리즈.*?',
            r'전체연재.*?',
            r'글씨 크게보기.*?',
            r'페이스북.*?',
            r'트위터.*?',
            r'공유하기.*?',
            r'추천.*?',
            r'댓글.*?',
            r'원고료로 응원.*?',
            r'최종 업데이트.*?',
            r'ㅣ.*?',
            r'\[이슈 분석\].*?',
            r'곽우신\(gorapakr\).*?',
            r'AD.*?',
            r'광고.*?',
            r'큰사진보기.*?',
            r'관련사진보기.*?',
            r'Please activate JavaScript.*?',
            r'LiveRe.*?',
            r'Copyright.*?',
            r'All rights reserved.*?'
        ]
        
        for pattern in unwanted_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.DOTALL)
        
        # 연속된 공백 정리
        content = re.sub(r'\s+', ' ', content).strip()
        
        return {
            'title': title,
            'content': content,
            'publish_date': publish_date
        }
    
    async def process_article(self, session, url):
        """개별 기사를 처리합니다."""
        try:
            html_content = await self.fetch_page(session, url)
            if not html_content:
                return None
            
            article_data = self.extract_article_content(html_content)
            
            if not article_data['title'] or not article_data['content']:
                return None
            
            # Supabase에 저장
            try:
                result = self.manager.client.table('articles').insert({
                    'issue_id': self.issue_id,
                    'media_id': self.media_id,
                    'title': article_data['title'],
                    'url': url,
                    'content': article_data['content'],
                    'bias': 'Left',  # 오마이뉴스는 Left bias
                    'published_at': article_data['publish_date']
                }).execute()
                
                if result.data:
                    return True
                else:
                    print(f"⚠️  기사 저장 실패: {url}")
                    return False
                    
            except Exception as e:
                print(f"❌ 기사 저장 오류: {url}, 오류: {e}")
                return False
                
        except Exception as e:
            print(f"❌ 기사 처리 오류: {url}, 오류: {e}")
            return False
    
    async def crawl_articles(self, target_count=100):
        """기사를 크롤링합니다."""
        print(f"🚀 오마이뉴스 정치 섹션 크롤링 시작 (목표: {target_count}개)")
        
        start_time = time.time()
        success_count = 0
        fail_count = 0
        
        # 미디어 아울렛 확인
        media_outlet = await self.get_media_outlet()
        if not media_outlet:
            print("❌ 미디어 아울렛 정보를 가져올 수 없습니다.")
            return
        
        print(f"📰 {media_outlet['name']} (ID: {self.media_id}) 크롤링 시작")
        
        # 페이지별로 기사 수집
        page = 1
        max_pages = 10  # 최대 10페이지까지
        
        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=50, limit_per_host=50),
            timeout=aiohttp.ClientTimeout(total=20)
        ) as session:
            
            while len(self.collected_articles) < target_count and page <= max_pages:
                # 페이지 URL 생성
                if page == 1:
                    page_url = self.politics_url
                else:
                    page_url = f"{self.politics_url}&pageno={page}"
                
                print(f"📄 {page}페이지 처리 중... ({len(self.collected_articles)}개 수집됨)")
                
                # 페이지 가져오기
                html_content = await self.fetch_page(session, page_url)
                if not html_content:
                    print(f"⚠️  {page}페이지 가져오기 실패")
                    page += 1
                    continue
                
                # 기사 링크 수집
                links = self.collect_article_links(html_content)
                if not links:
                    print(f"⚠️  {page}페이지에서 기사 링크를 찾을 수 없습니다.")
                    page += 1
                    continue
                
                print(f"🔗 {page}페이지에서 {len(links)}개 기사 링크 발견")
                
                # 기사 처리 (동시 처리) - 더 적극적으로
                tasks = []
                for link in links[:target_count - len(self.collected_articles)]:
                    task = self.process_article(session, link)
                    tasks.append(task)
                
                # 동시 실행 - 더 많은 기사를 동시에 처리
                if tasks:
                    # 50개씩 나누어서 처리 (메모리 효율성)
                    chunk_size = 50
                    for i in range(0, len(tasks), chunk_size):
                        chunk = tasks[i:i + chunk_size]
                        results = await asyncio.gather(*chunk, return_exceptions=True)
                        
                        for result in results:
                            if isinstance(result, Exception):
                                fail_count += 1
                            elif result:
                                success_count += 1
                            else:
                                fail_count += 1
                
                for result in results:
                    if isinstance(result, Exception):
                        fail_count += 1
                    elif result:
                        success_count += 1
                    else:
                        fail_count += 1
                
                # 목표 달성 확인
                if len(self.collected_articles) >= target_count:
                    break
                
                page += 1
                
                # 잠시 대기 (서버 부하 방지) - 최적화
                await asyncio.sleep(0.2)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        print(f"\n🎉 오마이뉴스 크롤링 완료!")
        print(f"⏱️  소요 시간: {elapsed_time:.2f}초")
        print(f"✅ 성공: {success_count}개")
        print(f"❌ 실패: {fail_count}개")
        print(f"📊 총 수집: {len(self.collected_articles)}개")
        
        if elapsed_time <= 20:
            print(f"🎯 목표 달성! 20초 이내 완료 ({elapsed_time:.2f}초)")
        else:
            print(f"⚠️  목표 초과: 20초 초과 ({elapsed_time:.2f}초)")
        
        return success_count


    async def collect_all_articles(self) -> List[Dict]:
        """모든 기사 수집 (표준 인터페이스)"""
        try:
            result = await self.crawl_articles()
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
                if hasattr(self, 'manager') and self.manager:
                    if self.manager.insert_article(article):
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
    crawler = OhMyNewsPoliticsCrawler()
    await crawler.crawl_articles(100)

if __name__ == "__main__":
    asyncio.run(main())
