#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SBS 정치 섹션 크롤러 (비동기 최적화 버전)

### 조건:
1. **비동기 방식 (asyncio + httpx + BeautifulSoup) 사용**
   - 기사 리스트를 병렬로 빠르게 수집해야 함
   - 전체 실행 시간은 20초 이내 목표

2. **HTML 구조**
   - 기사 목록 페이지 URL: https://news.sbs.co.kr/news/newsSection.do?pageIdx=1&sectionType=01&pageDate=20250822
   - 기사 제목: `strong.tit_line`
   - 기사 링크: `a[href*='news/endPage.do']`
   - 기사 날짜: `span.date`
   - 기사 본문: `div.text_area`

3. **타임아웃**
   - 요청 timeout은 5초 이내로 설정
   - 실패한 요청은 건너뛰고 로그 출력

4. **중복 제거**
   - 같은 기사 링크는 한 번만 저장

5. **출력 형태**
   - JSON 리스트로 저장: `[{"title": "...", "url": "...", "date": "...", "content": "..."}]`

6. **성능 최적화**
   - 기사 50개 수집 시 20초 이내 완료
   - 필요시 `asyncio.gather` 활용
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

import asyncio
import httpx
import json
import re
from datetime import datetime
from typing import List, Dict, Optional, Set
import logging
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from utils.legacy.supabase_manager_v2 import SupabaseManagerV2

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SBSPoliticsCrawler:
    def __init__(self):
        self.articles = []
        self.seen_urls: Set[str] = set()
        self.collected_count = 0
        self.target_count = 50
        
        # Supabase 연결
        self.supabase_manager = SupabaseManagerV2()
        
        # SBS 설정
        self.base_url = "https://news.sbs.co.kr"
        self.section_url = "https://news.sbs.co.kr/news/newsSection.do"
        self.section_type = "01"  # 정치 섹션
        self.media_name = "SBS"
        self.media_id = 14  # SBS media_id 고정값
        
        # 크롤링 설정
        self.max_pages = 5  # 최대 5페이지까지만 탐색
        self.articles_per_page = 10  # 페이지당 기사 수
        self.timeout = 5.0  # 5초 타임아웃
        self.max_concurrent_requests = 10  # 동시 요청 수
        
        # 오류 카운터
        self.network_errors = 0
        self.parsing_errors = 0
        self.content_errors = 0
        
    def clean_content(self, text: str) -> str:
        """본문 내용 정제"""
        if not text:
            return ""
        
        # <br> 태그를 줄바꿈으로 변환
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        
        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', text)
        
        # 특정 문구 제거
        remove_patterns = [
            r'Copyright\s*Ⓒ\s*SBS',
            r'Copyright\s*©\s*SBS',
            r'ⓒ\s*SBS',
            r'저작권자\s*©\s*SBS',
            r'무단\s*전재\s*및\s*재배포\s*금지',
            r'기자\s*이메일',
            r'기자\s*연락처',
            r'기자\s*카드',
            r'댓글',
            r'광고',
            r'배너',
            r'SNS',
            r'공유하기',
            r'추천하기'
        ]
        
        for pattern in remove_patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        # 여러 줄바꿈을 하나로 정리
        text = re.sub(r'\n+', '\n', text)
        
        # 앞뒤 공백 제거
        text = text.strip()
        
        return text
    
    def parse_date(self, date_text: str) -> str:
        """날짜 텍스트를 ISO 포맷으로 변환"""
        try:
            # SBS 날짜 형식: "2025.08.22" 또는 "08.22"
            if date_text:
                # 현재 연도 추가
                if len(date_text.split('.')) == 2:
                    current_year = datetime.now().year
                    date_text = f"{current_year}.{date_text}"
                
                # ISO 포맷으로 변환
                dt = datetime.strptime(date_text, "%Y.%m.%d")
                return dt.isoformat()
        except:
            pass
        
        # 변환 실패 시 현재 시간 반환
        return datetime.now().isoformat()
    
    async def fetch_page(self, client: httpx.AsyncClient, page_idx: int) -> Optional[str]:
        """특정 페이지 HTML 가져오기"""
        try:
            # 오늘 날짜
            today = datetime.now().strftime("%Y%m%d")
            
            # 페이지 URL 구성
            url = f"{self.section_url}?pageIdx={page_idx}&sectionType={self.section_type}&pageDate={today}"
            
            # 페이지 요청
            response = await client.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            return response.text
            
        except Exception as e:
            logger.warning(f"페이지 {page_idx} 요청 실패: {e}")
            self.network_errors += 1
            return None
    
    def parse_article_links(self, html: str, page_idx: int) -> List[Dict]:
        """HTML에서 기사 링크 파싱"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 기사 제목과 링크 추출
            articles = []
            
            articles = []
            
            # 1. w_r 클래스의 주요뉴스 4개 수집
            main_news = soup.select('div.w_r ul.news li')
            logger.info(f"  - 주요뉴스 (w_r): {len(main_news)}개")
            
            for news_item in main_news:
                # 링크 추출: a 태그의 href
                link_elem = news_item.select_one('a[href*="news/endPage.do"]')
                if not link_elem:
                    continue
                    
                url = link_elem.get('href', '')
                if not url:
                    continue
                
                # 제목 추출: a 태그의 텍스트
                title = link_elem.get_text(strip=True)
                if not title:
                    continue
                
                # 절대 URL로 변환
                if url.startswith('/'):
                    url = f"https://news.sbs.co.kr{url}"
                elif not url.startswith('http'):
                    url = f"https://news.sbs.co.kr/{url}"
                
                # 중복 체크
                if url in self.seen_urls:
                    continue
                
                articles.append({
                    'title': title,
                    'url': url,
                    'date': '',  # 주요뉴스는 날짜 정보가 없음
                    'page_idx': page_idx
                })
                logger.info(f"    주요뉴스 추가: {title[:30]}...")
            
            # 2. w_inner 클래스의 일반 기사 수집
            list_news = soup.select('div.w_inner a.news[href*="news/endPage.do"]')
            logger.info(f"  - 일반 기사 (w_inner): {len(list_news)}개")
            
            for news_item in list_news:
                url = news_item.get('href', '')
                if not url:
                    continue
                
                # 제목 추출: 같은 부모 요소에서 strong.sub 찾기
                title_elem = news_item.select_one('strong.sub')
                if not title_elem:
                    continue
                    
                title = title_elem.get_text(strip=True)
                if not title:
                    continue
                
                # 날짜 추출: 같은 부모 요소에서 span.date 찾기
                date_elem = news_item.select_one('span.date')
                date_text = date_elem.get_text(strip=True) if date_elem else ''
                
                # 절대 URL로 변환
                if url.startswith('/'):
                    url = f"https://news.sbs.co.kr{url}"
                elif not url.startswith('http'):
                    url = f"https://news.sbs.co.kr/{url}"
                
                # 중복 체크
                if url in self.seen_urls:
                    continue
                
                articles.append({
                    'title': title,
                    'url': url,
                    'date': date_text,
                    'page_idx': page_idx
                })
            
            return articles
            
        except Exception as e:
            logger.error(f"HTML 파싱 실패 (페이지 {page_idx}): {e}")
            self.parsing_errors += 1
            return []
    
    async def fetch_article_content(self, client: httpx.AsyncClient, article_info: Dict) -> Optional[Dict]:
        """기사 상세 페이지에서 본문 추출"""
        try:
            # 기사 페이지 요청
            response = await client.get(article_info['url'], timeout=self.timeout)
            response.raise_for_status()
            
            # HTML 파싱
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 본문 영역 찾기: div.text_area
            content_area = soup.select_one('div.text_area')
            
            if not content_area:
                logger.warning(f"본문 영역을 찾을 수 없습니다: {article_info['title'][:30]}...")
                self.content_errors += 1
                return None
            
            # 본문 내용 추출
            content_html = str(content_area)
            clean_content = self.clean_content(content_html)
            
            if not clean_content or len(clean_content.strip()) < 50:
                logger.warning(f"본문 내용이 너무 짧습니다: {article_info['title'][:30]}...")
                self.content_errors += 1
                return None
            
            # 날짜 파싱
            published_at = self.parse_date(article_info['date'])
            
            # 기사 데이터 구성
            article_data = {
                'title': article_info['title'],
                'url': article_info['url'],
                'date': article_info['date'],
                'content': clean_content,
                'published_at': published_at,
                'page_idx': article_info['page_idx']
            }
            
            return article_data
            
        except Exception as e:
            logger.error(f"기사 내용 추출 실패: {article_info['title'][:30]}... - {e}")
            self.content_errors += 1
            return None
    
    async def collect_all_articles(self) -> List[Dict]:
        """모든 기사 수집 (병렬 처리)"""
        logger.info(f"🚀 SBS 정치 뉴스 크롤링 시작")
        logger.info(f"🎯 목표: {self.target_count}개 기사")
        logger.info(f"📰 최대 페이지: {self.max_pages}페이지")
        logger.info(f"⚡ 동시 요청 수: {self.max_concurrent_requests}")
        
        start_time = datetime.now()
        
        try:
            # httpx 클라이언트 설정
            limits = httpx.Limits(max_connections=self.max_concurrent_requests)
            timeout = httpx.Timeout(self.timeout)
            
            async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
                
                # 1단계: 모든 페이지에서 기사 링크 수집
                logger.info("📄 1단계: 기사 링크 수집 중...")
                
                # seen_urls 초기화 (새로운 실행마다)
                self.seen_urls.clear()
                
                page_tasks = []
                for page_idx in range(1, self.max_pages + 1):
                    task = self.fetch_page(client, page_idx)
                    page_tasks.append(task)
                
                # 병렬로 페이지 요청
                page_results = await asyncio.gather(*page_tasks, return_exceptions=True)
                
                # 기사 링크 파싱
                all_article_links = []
                for i, result in enumerate(page_results, 1):
                    if isinstance(result, Exception):
                        logger.warning(f"페이지 {i} 처리 실패: {result}")
                        continue
                    
                    if result:
                        article_links = self.parse_article_links(result, i)
                        all_article_links.extend(article_links)
                        logger.info(f"페이지 {i}: {len(article_links)}개 기사 링크 발견")
                
                logger.info(f"✅ 총 {len(all_article_links)}개 기사 링크 수집 완료")
                
                # 2단계: 기사 본문 병렬 수집
                logger.info("📰 2단계: 기사 본문 수집 중...")
                
                # 중복 제거
                unique_articles = []
                for article in all_article_links:
                    if article['url'] not in self.seen_urls:
                        unique_articles.append(article)
                        self.seen_urls.add(article['url'])
                
                logger.info(f"중복 제거 후: {len(unique_articles)}개 기사")
                
                # 목표 개수만큼만 처리
                target_articles = unique_articles[:self.target_count]
                
                # 기사 본문 병렬 수집
                content_tasks = []
                for article in target_articles:
                    task = self.fetch_article_content(client, article)
                    content_tasks.append(task)
                
                # 병렬로 본문 요청
                content_results = await asyncio.gather(*content_tasks, return_exceptions=True)
                
                # 성공한 결과만 수집
                for i, result in enumerate(content_results):
                    if isinstance(result, Exception):
                        logger.warning(f"기사 {i+1} 처리 실패: {result}")
                        continue
                    
                    if result:
                        self.articles.append(result)
                        self.collected_count += 1
                        
                        if self.collected_count % 10 == 0:
                            logger.info(f"✅ {self.collected_count}개 기사 수집 완료")
                
                # 수집 완료 시간
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                logger.info(f"🎉 크롤링 완료!")
                logger.info(f"📊 수집 결과: {self.collected_count}개 기사")
                logger.info(f"⏱️ 소요 시간: {duration:.1f}초")
                logger.info(f"🚀 평균 속도: {self.collected_count / duration:.1f} 기사/초" if duration > 0 else "🚀 평균 속도: 0.0 기사/초")
                
                return self.articles
                
        except Exception as e:
            logger.error(f"크롤링 실행 중 오류 발생: {e}")
            return self.articles
    
    async def save_to_supabase(self, articles: List[Dict]) -> Dict[str, int]:
        """Supabase에 기사 저장"""
        if not articles:
            return {"success": 0, "failed": 0, "total": 0}
        
        success_count = 0
        failed_count = 0
        
        for article in articles:
            try:
                # Supabase 형식으로 데이터 변환
                article_data = {
                    'title': article['title'],
                    'url': article['url'],
                    'content': article['content'],
                    'published_at': article['published_at'],
                    'media_id': self.media_id,
                    'bias': 'Center',  # SBS는 중도
                    'issue_id': 1  # 기본값
                }
                
                # 기사 저장
                result = self.supabase_manager.insert_article(article_data)
                if result:
                    success_count += 1
                    logger.info(f"새 기사 저장: {article['title'][:50]}...")
                else:
                    failed_count += 1
                    
            except Exception as e:
                logger.error(f"기사 저장 실패: {e}")
                failed_count += 1
        
        return {
            "success": success_count,
            "failed": failed_count,
            "total": len(articles)
        }
    
    def save_to_json(self, articles: List[Dict], filename: str = "sbs_articles.json"):
        """JSON 파일로 저장"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(articles, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ {len(articles)}개 기사를 {filename}에 저장 완료")
        except Exception as e:
            logger.error(f"JSON 저장 실패: {e}")
    
    def display_results(self, articles: List[Dict], save_results: Dict[str, int], duration: float):
        """수집 결과 출력"""
        print("\n" + "="*60)
        print("      SBS 정치 뉴스 크롤링 완료!      ")
        print("="*60)
        print(f"📊 수집 결과:")
        print(f"  • 총 기사 수: {len(articles)}개")
        print(f"  • 소요 시간: {duration:.1f}초")
        print(f"  • 평균 속도: {len(articles) / duration:.1f} 기사/초" if duration > 0 else "  • 평균 속도: 0.0 기사/초")
        print(f"  • 네트워크 오류: {self.network_errors}회")
        print(f"  • 파싱 오류: {self.parsing_errors}회")
        print(f"  • 본문 오류: {self.content_errors}회")
        
        # 목표 달성 여부
        if len(articles) >= self.target_count:
            print(f"  • 🎯 목표 달성: {self.target_count}개 이상")
        else:
            print(f"  • ⚠️ 목표 미달성: {len(articles)}개 (목표: {self.target_count}개)")
        
        # 저장 결과
        print(f"\n💾 Supabase 저장 결과:")
        print(f"  • 성공: {save_results['success']}개")
        print(f"  • 실패: {save_results['failed']}개")
        print(f"  • 총 기사: {save_results['total']}개")
        
        if save_results['success'] > 0:
            print(f"✅ {save_results['success']}개 기사가 Supabase에 성공적으로 저장되었습니다!")
        
        # 수집된 기사 제목 일부 출력
        if articles:
            print(f"\n📰 수집된 기사 제목 (처음 10개):")
            for i, article in enumerate(articles[:10], 1):
                title = article['title']
                title_preview = title[:60] + "..." if len(title) > 60 else title
                print(f"  {i}. {title_preview}")
            
            if len(articles) > 10:
                print(f"  ... 외 {len(articles) - 10}개 기사")
        
        print("\n🎉 SBS 정치 뉴스 크롤링 완료!")
        print("💾 Supabase에 저장 완료!")

async def main():
    """메인 실행 함수"""
    try:
        crawler = SBSPoliticsCrawler()
        
        # 시작 시간 기록
        start_time = datetime.now()
        
        # 뉴스 수집
        articles = await crawler.collect_all_articles()
        
        # 수집 완료 시간
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Supabase 저장
        save_results = await crawler.save_to_supabase(articles)
        
        # JSON 파일로도 저장
        crawler.save_to_json(articles)
        
        # 결과 출력
        crawler.display_results(articles, save_results, duration)
        
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 크롤링이 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 크롤링 중 오류 발생: {e}")
        logger.error(f"크롤링 오류: {e}")

if __name__ == "__main__":
    asyncio.run(main())
