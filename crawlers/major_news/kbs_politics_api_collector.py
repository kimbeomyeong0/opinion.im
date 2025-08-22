#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KBS 정치 뉴스 API 수집기

### 조건
- 오늘자 기사만 수집 (datetimeBegin=오늘 00시, datetimeEnd=오늘 23:59:59)
- 상단 고정 기사(rowsPerPage=5)와 하단 리스트(rowsPerPage=12, 페이지네이션 포함)를 모두 수집
- 정치 섹션 코드(contentsCode=0003)만 가져와
- 중복은 제거 (articles.url 기준, Supabase 조회 후 insert)
- 기사 본문은 newsContents 필드를 우선 사용하고, 없으면 originNewsContents를 써
- 본문 안의 <br>은 줄바꿈(\n)으로 바꾸고, 다른 HTML 태그는 제거
- Supabase articles 테이블에 저장

### Supabase 저장 규칙
- title → newsTitle
- url → https://news.kbs.co.kr/news/pc/view/view.do?ncd={newsCode}
- content → newsContents 또는 originNewsContents (정제 후)
- published_at → serviceTime
- media_id → 15
- bias → center

### API 엔드포인트
- 상단 고정 기사: https://news.kbs.co.kr/api/getNewsList?currentPageNo=1&rowsPerPage=5&exceptPhotoYn=Y&contentsExpYn=Y&datetimeBegin=YYYYMMDD000000&datetimeEnd=YYYYMMDD235959&contentsCode=0003
- 하단 리스트: https://news.kbs.co.kr/api/getNewsList?currentPageNo={page}&rowsPerPage=12&exceptPhotoYn=Y&datetimeBegin=YYYYMMDD000000&datetimeEnd=YYYYMMDD235959&contentsCode=0003&localCode=00
- 기사 상세: https://news.kbs.co.kr/api/getNews?id={newsCode}
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))

import asyncio
import httpx
import re
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
import logging
from tqdm import tqdm
from utils.supabase_manager_unified import UnifiedSupabaseManager

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class KBSPoliticsAPICollector:
    def __init__(self):
        self.articles = []
        self.seen_urls: Set[str] = set()
        
        # Supabase 연결
        self.supabase_manager = UnifiedSupabaseManager()
        
        # 오늘 날짜 설정
        self.today = datetime.now()
        self.date_str = self.today.strftime("%Y%m%d")
        self.datetime_begin = f"{self.date_str}000000"
        self.datetime_end = f"{self.date_str}235959"
        
        # API 설정
        self.contents_code = "0003"  # 정치 섹션
        self.media_id = 15  # KBS media_id
        self.media_bias = "center"
        
        # API 엔드포인트
        self.fixed_news_url = "https://news.kbs.co.kr/api/getNewsList"
        self.list_news_url = "https://news.kbs.co.kr/api/getNewsList"
        self.detail_news_url = "https://news.kbs.co.kr/api/getNews"
        
        # 성능 최적화
        self.max_concurrent_requests = 5
        self.timeout = httpx.Timeout(30.0)
        
        # 오류 카운터
        self.network_errors = 0
        self.parsing_errors = 0
        
    def clean_html_content(self, text: str) -> str:
        """HTML 태그 제거 및 <br>을 줄바꿈으로 변환"""
        if not text:
            return ""
        
        # <br> 태그를 줄바꿈으로 변환
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        
        # 다른 HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', text)
        
        # 여러 줄바꿈을 하나로 정리
        text = re.sub(r'\n+', '\n', text)
        
        # 앞뒤 공백 제거
        text = text.strip()
        
        return text
    
    def build_article_url(self, news_id: str) -> str:
        """기사 URL 생성"""
        return f"https://news.kbs.co.kr/news/pc/view/view.do?ncd={news_id}"
    
    def convert_service_time_to_iso(self, service_time: str) -> str:
        """KBS serviceTime을 ISO 포맷으로 변환"""
        try:
            # serviceTime 형식: "2025-08-22 14:30:00"
            dt = datetime.strptime(service_time, "%Y-%m-%d %H:%M:%S")
            return dt.isoformat()
        except Exception as e:
            logger.warning(f"날짜 변환 실패: {service_time}, 오류: {e}")
            # 현재 시간으로 대체
            return datetime.now().isoformat()
    
    async def fetch_fixed_news(self, client: httpx.AsyncClient) -> List[Dict]:
        """상단 고정 기사 가져오기"""
        params = {
            "currentPageNo": 1,
            "rowsPerPage": 5,
            "exceptPhotoYn": "Y",
            "contentsExpYn": "Y",
            "datetimeBegin": self.datetime_begin,
            "datetimeEnd": self.datetime_end,
            "contentsCode": self.contents_code
        }
        
        try:
            response = await client.get(self.fixed_news_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"상단 고정 기사 API 응답: {data.get('success', False)}")
            
            if data.get('success') and 'data' in data:
                return data['data']
            else:
                logger.warning("상단 고정 기사 API 응답에 데이터가 없습니다.")
                return []
                
        except Exception as e:
            logger.error(f"상단 고정 기사 API 요청 실패: {e}")
            self.network_errors += 1
            return []
    
    async def fetch_list_news_page(self, client: httpx.AsyncClient, page: int) -> List[Dict]:
        """하단 리스트 기사 가져오기 (페이지별)"""
        params = {
            "currentPageNo": page,
            "rowsPerPage": 12,
            "exceptPhotoYn": "Y",
            "datetimeBegin": self.datetime_begin,
            "datetimeEnd": self.datetime_end,
            "contentsCode": self.contents_code,
            "localCode": "00"
        }
        
        try:
            response = await client.get(self.list_news_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            logger.info(f"하단 리스트 페이지 {page} API 응답: {data.get('success', False)}")
            
            if data.get('success') and 'data' in data:
                return data['data']
            else:
                logger.warning(f"하단 리스트 페이지 {page} API 응답에 데이터가 없습니다.")
                return []
                
        except Exception as e:
            logger.error(f"하단 리스트 페이지 {page} API 요청 실패: {e}")
            self.network_errors += 1
            return []
    
    async def fetch_news_detail(self, client: httpx.AsyncClient, news_id: str) -> Optional[Dict]:
        """기사 상세 정보 가져오기"""
        params = {"id": news_id}
        
        try:
            response = await client.get(self.detail_news_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            data = response.json()
            if data.get('success') and 'data' in data:
                return data['data']
            else:
                logger.warning(f"기사 상세 API 응답에 데이터가 없습니다: {news_id}")
                return None
                
        except Exception as e:
            logger.error(f"기사 상세 API 요청 실패 {news_id}: {e}")
            self.network_errors += 1
            return None
    
    def parse_news_item(self, news_item: Dict, detail_data: Optional[Dict] = None) -> Optional[Dict]:
        """뉴스 아이템 파싱"""
        try:
            # 필수 필드 확인
            if not all(key in news_item for key in ["newsTitle", "newsCode", "serviceTime"]):
                logger.warning(f"필수 필드 누락: {news_item.get('newsTitle', '제목 없음')}")
                return None
            
            news_id = news_item["newsCode"]
            title = news_item["newsTitle"]
            service_time = news_item["serviceTime"]
            
            # 기사 URL 생성
            article_url = self.build_article_url(news_id)
            
            # 중복 체크
            if article_url in self.seen_urls:
                logger.info(f"중복 기사 건너뛰기: {title[:30]}...")
                return None
            
            # 본문 추출 (상세 API 우선, 없으면 기본 필드)
            content = ""
            if detail_data and "newsContents" in detail_data and detail_data["newsContents"]:
                content = detail_data["newsContents"]
            elif detail_data and "originNewsContents" in detail_data and detail_data["originNewsContents"]:
                content = detail_data["originNewsContents"]
            elif "newsContents" in news_item and news_item["newsContents"]:
                content = news_item["newsContents"]
            elif "originNewsContents" in news_item and news_item["originNewsContents"]:
                content = news_item["originNewsContents"]
            
            # HTML 태그 정제
            clean_content = self.clean_html_content(content)
            
            # 날짜 변환
            published_at = self.convert_service_time_to_iso(service_time)
            
            # 기사 데이터 구성
            article_data = {
                "title": title,
                "url": article_url,
                "content": clean_content,
                "published_at": published_at,
                "news_id": news_id,
                "raw_data": news_item
            }
            
            return article_data
            
        except Exception as e:
            logger.error(f"뉴스 아이템 파싱 실패: {e}")
            self.parsing_errors += 1
            return None
    
    async def collect_all_news(self) -> List[Dict]:
        """모든 뉴스 기사 수집"""
        logger.info(f"🚀 KBS 정치 뉴스 API 수집 시작")
        logger.info(f"📅 대상 날짜: {self.date_str}")
        logger.info(f"⏰ 시간 범위: {self.datetime_begin} ~ {self.datetime_end}")
        
        all_articles = []
        
        async with httpx.AsyncClient(
            timeout=self.timeout,
            limits=httpx.Limits(max_connections=self.max_concurrent_requests)
        ) as client:
            
            # 1. 상단 고정 기사 수집
            logger.info("📰 상단 고정 기사 수집 중...")
            fixed_news = await self.fetch_fixed_news(client)
            
            for news_item in fixed_news:
                # 상세 정보 가져오기
                detail_data = await self.fetch_news_detail(client, news_item["newsCode"])
                
                # 기사 파싱
                article = self.parse_news_item(news_item, detail_data)
                if article:
                    all_articles.append(article)
                    self.seen_urls.add(article["url"])
                    logger.info(f"✅ 고정 기사 수집: {article['title'][:50]}...")
                
                # API 부하 방지를 위한 짧은 대기
                await asyncio.sleep(0.2)
            
            logger.info(f"✅ 상단 고정 기사: {len(fixed_news)}개 수집 완료")
            
            # 2. 하단 리스트 기사 수집 (페이지네이션)
            logger.info("📰 하단 리스트 기사 수집 중...")
            page = 1
            max_pages = 10  # 최대 10페이지까지만 시도
            
            with tqdm(desc="하단 리스트 수집", unit="페이지") as pbar:
                while page <= max_pages:
                    pbar.set_description(f"페이지 {page} 수집 중")
                    
                    # 페이지별 기사 가져오기
                    page_news = await self.fetch_list_news_page(client, page)
                    
                    if not page_news:
                        logger.info(f"페이지 {page}에서 더 이상 기사가 없습니다.")
                        break
                    
                    new_articles_count = 0
                    for news_item in page_news:
                        # 상세 정보 가져오기
                        detail_data = await self.fetch_news_detail(client, news_item["newsCode"])
                        
                        # 기사 파싱
                        article = self.parse_news_item(news_item, detail_data)
                        if article:
                            all_articles.append(article)
                            self.seen_urls.add(article["url"])
                            new_articles_count += 1
                            logger.info(f"✅ 리스트 기사 수집: {article['title'][:50]}...")
                        
                        # API 부하 방지를 위한 짧은 대기
                        await asyncio.sleep(0.2)
                    
                    logger.info(f"✅ 페이지 {page}: {new_articles_count}개 새 기사 수집 (총 {len(all_articles)}개)")
                    
                    if new_articles_count == 0:
                        logger.info("더 이상 새 기사가 없습니다.")
                        break
                    
                    page += 1
                    pbar.update(1)
                    
                    # 페이지 간 대기
                    await asyncio.sleep(0.5)
        
        return all_articles
    
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
                    'bias': self.media_bias,
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
    
    def display_results(self, articles: List[Dict], save_results: Dict[str, int], duration: float):
        """수집 결과 출력"""
        print("\n" + "="*60)
        print("      KBS 정치 뉴스 API 수집 완료!      ")
        print("="*60)
        print(f"📊 수집 결과:")
        print(f"  • 총 기사 수: {len(articles)}개")
        print(f"  • 소요 시간: {duration:.1f}초")
        print(f"  • 평균 속도: {len(articles) / duration:.1f} 기사/초" if duration > 0 else "  • 평균 속도: 0.0 기사/초")
        print(f"  • 네트워크 오류: {self.network_errors}회")
        print(f"  • 파싱 오류: {self.parsing_errors}회")
        
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
        
        print("\n🎉 KBS 정치 뉴스 API 수집 완료!")
        print("💾 Supabase에 저장 완료!")

async def main():
    """메인 실행 함수"""
    try:
        collector = KBSPoliticsAPICollector()
        
        # 시작 시간 기록
        start_time = datetime.now()
        
        # 뉴스 수집
        articles = await collector.collect_all_news()
        
        # 수집 완료 시간
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # Supabase 저장
        save_results = await collector.save_to_supabase(articles)
        
        # 결과 출력
        collector.display_results(articles, save_results, duration)
        
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 수집이 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 수집 중 오류 발생: {e}")
        logger.error(f"수집 오류: {e}")

if __name__ == "__main__":
    asyncio.run(main())
