#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JTBC 정치 뉴스 API 수집기
JTBC 뉴스 API에서 정치 섹션 기사를 수집하여 Supabase에 저장
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
from utils.supabase_manager_unified import UnifiedSupabaseManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JTBCPoliticsCollector:
    def __init__(self):
        self.articles = []
        self.seen_urls: Set[str] = set()
        self.collected_count = 0
        self.target_count = 50
        self.supabase_manager = UnifiedSupabaseManager()
        
        # JTBC 설정
        self.base_url = "https://news-api.jtbc.co.kr"
        self.api_endpoint = "/v1/get/contents/section/list/articles"
        self.media_name = "JTBC"
        self.media_id = 13  # JTBC media_id (media_outlets 테이블 기준)
        
        # API 설정
        self.max_pages = 5  # 최대 5페이지 (기사 50개 목표)
        self.page_size = 10  # 페이지당 기사 수
        self.timeout = 5.0  # 5초 타임아웃
        self.max_concurrent_requests = 10
        
        # 에러 카운터
        self.network_errors = 0
        self.parsing_errors = 0
        self.content_errors = 0

    def clean_content(self, text: str) -> str:
        """기사 내용 정제"""
        if not text:
            return ""
        
        # HTML 태그 제거
        text = re.sub(r'<[^>]+>', '', text)
        # 특수 문자 정리
        text = text.replace('&hellip;', '...').replace('&quot;', '"')
        # 연속된 공백 정리
        text = re.sub(r'\s+', ' ', text)
        # 앞뒤 공백 제거
        text = text.strip()
        
        return text

    def parse_date(self, date_text: str) -> str:
        """날짜 파싱 (ISO 형식으로 변환)"""
        if not date_text:
            return datetime.now().isoformat()
        
        try:
            # "2025-08-22T11:33" 형식을 ISO 형식으로 변환
            dt = datetime.fromisoformat(date_text)
            return dt.isoformat()
        except Exception as e:
            logger.warning(f"날짜 파싱 실패: {date_text}, 오류: {e}")
            return datetime.now().isoformat()

    def construct_article_url(self, article_idx: str) -> str:
        """기사 URL 생성"""
        return f"https://news.jtbc.co.kr/article/{article_idx}"

    async def fetch_page(self, client: httpx.AsyncClient, page_no: int) -> Optional[Dict]:
        """API 페이지 요청"""
        try:
            params = {
                'pageNo': page_no,
                'sectionEngName': 'politics',
                'articleListType': 'ARTICLE',
                'pageSize': self.page_size
            }
            
            url = f"{self.base_url}{self.api_endpoint}"
            response = await client.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            return response.json()
            
        except httpx.TimeoutException:
            logger.warning(f"페이지 {page_no} 요청 타임아웃")
            self.network_errors += 1
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(f"페이지 {page_no} HTTP 오류: {e.response.status_code}")
            self.network_errors += 1
            return None
        except Exception as e:
            logger.warning(f"페이지 {page_no} 요청 실패: {e}")
            self.network_errors += 1
            return None

    def parse_articles(self, api_response: Dict, page_no: int) -> List[Dict]:
        """API 응답에서 기사 정보 파싱"""
        articles = []
        
        try:
            if api_response.get('resultCode') != '00':
                logger.warning(f"페이지 {page_no} API 오류: {api_response.get('resultMessage', '알 수 없는 오류')}")
                return articles
            
            data = api_response.get('data', {})
            article_list = data.get('list', [])
            
            logger.info(f"  - 페이지 {page_no}: {len(article_list)}개 기사 발견")
            
            for article in article_list:
                try:
                    # 필수 필드 확인
                    article_idx = article.get('articleIdx')
                    title = article.get('articleTitle')
                    
                    if not article_idx or not title:
                        continue
                    
                    # 기사 URL 생성
                    article_url = self.construct_article_url(article_idx)
                    
                    # 중복 체크
                    if article_url in self.seen_urls:
                        continue
                    
                    # 기사 정보 추출
                    article_data = {
                        'id': article_idx,
                        'title': title,
                        'summary': self.clean_content(article.get('articleInnerTextContent', '')),
                        'url': article_url,
                        'thumbnail': article.get('articleThumbnailImgUrl', ''),
                        'published_at': self.parse_date(article.get('publicationDate')),
                        'reporter': article.get('journalistName', ''),
                        'page_no': page_no
                    }
                    
                    articles.append(article_data)
                    self.seen_urls.add(article_url)
                    
                except Exception as e:
                    logger.warning(f"기사 파싱 실패 (페이지 {page_no}): {e}")
                    self.parsing_errors += 1
                    continue
            
        except Exception as e:
            logger.error(f"페이지 {page_no} 응답 파싱 실패: {e}")
            self.parsing_errors += 1
        
        return articles

    async def collect_all_articles(self) -> List[Dict]:
        """모든 페이지에서 기사 수집"""
        start_time = datetime.now()
        
        try:
            # HTTP 클라이언트 설정
            limits = httpx.Limits(max_connections=self.max_concurrent_requests)
            timeout = httpx.Timeout(self.timeout)
            
            async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
                
                # 1단계: 모든 페이지에서 기사 수집
                logger.info("📄 1단계: 기사 수집 중...")
                
                page_tasks = []
                for page_no in range(1, self.max_pages + 1):
                    task = self.fetch_page(client, page_no)
                    page_tasks.append(task)
                
                # 병렬로 페이지 요청
                page_results = await asyncio.gather(*page_tasks, return_exceptions=True)
                
                # 기사 파싱
                all_articles = []
                for i, result in enumerate(page_results, 1):
                    if isinstance(result, Exception):
                        logger.warning(f"페이지 {i} 처리 실패: {result}")
                        continue
                    
                    if result:
                        articles = self.parse_articles(result, i)
                        all_articles.extend(articles)
                
                logger.info(f"✅ 총 {len(all_articles)}개 기사 수집 완료")
                
                # 목표 개수만큼만 처리
                target_articles = all_articles[:self.target_count]
                
                # 수집 완료 시간
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                logger.info(f"🎉 수집 완료!")
                logger.info(f"📊 수집 결과: {len(target_articles)}개 기사")
                logger.info(f"⏱️ 소요 시간: {duration:.1f}초")
                logger.info(f"🚀 평균 속도: {len(target_articles) / duration:.1f} 기사/초" if duration > 0 else "🚀 평균 속도: 0.0 기사/초")
                
                return target_articles
                
        except Exception as e:
            logger.error(f"수집 실행 중 오류 발생: {e}")
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
                    'content': article['summary'],  # 요약을 본문으로 사용
                    'published_at': article['published_at'],
                    'media_id': self.media_id,
                    'bias': 'Center',  # JTBC는 중도
                    'issue_id': 1  # 기본값
                }
                
                # 기사 저장
                result = self.supabase_manager.insert_article(article_data)
                
                if result:
                    success_count += 1
                    logger.info(f"기사 저장 성공: {article['title'][:50]}...")
                else:
                    failed_count += 1
                    logger.warning(f"기사 저장 실패: {article['title'][:50]}...")
                
            except Exception as e:
                failed_count += 1
                logger.error(f"기사 저장 중 오류: {e}")
                continue
        
        return {"success": success_count, "failed": failed_count, "total": len(articles)}

    def save_to_json(self, articles: List[Dict], filename: str = "jtbc_articles.json"):
        """기사를 JSON 파일로 저장"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(articles, f, ensure_ascii=False, indent=2)
            logger.info(f"✅ {len(articles)}개 기사를 {filename}에 저장 완료")
        except Exception as e:
            logger.error(f"JSON 저장 실패: {e}")

    def display_results(self, articles: List[Dict], save_results: Dict[str, int], duration: float):
        """결과 출력"""
        print("=" * 60)
        print("      JTBC 정치 뉴스 API 수집 완료!      ")
        print("=" * 60)
        print(f"📊 수집 결과:")
        print(f"  • 총 기사 수: {len(articles)}개")
        print(f"  • 소요 시간: {duration:.1f}초")
        print(f"  • 평균 속도: {len(articles) / duration:.1f} 기사/초" if duration > 0 else "  • 평균 속도: 0.0 기사/초")
        print(f"  • 네트워크 오류: {self.network_errors}회")
        print(f"  • 파싱 오류: {self.parsing_errors}회")
        print(f"  • 목표 달성: {'✅' if len(articles) >= self.target_count else '⚠️'} {len(articles)}개 (목표: {self.target_count}개)")
        print()
        
        if save_results:
            print(f"💾 Supabase 저장 결과:")
            print(f"  • 성공: {save_results['success']}개")
            print(f"  • 실패: {save_results['failed']}개")
            print(f"  • 총 기사: {save_results['total']}개")
            print(f"✅ {save_results['success']}개 기사가 Supabase에 성공적으로 저장되었습니다!")
            print()
        
        if articles:
            print(f"📰 수집된 기사 제목 (처음 10개):")
            for i, article in enumerate(articles[:10], 1):
                print(f"  {i}. {article['title'][:50]}...")
            if len(articles) > 10:
                print(f"  ... 외 {len(articles) - 10}개 기사")
            print()
        
        print("🎉 JTBC 정치 뉴스 API 수집 완료!")
        if save_results and save_results['success'] > 0:
            print("💾 Supabase에 저장 완료!")

async def main():
    """메인 함수"""
    collector = JTBCPoliticsCollector()
    
    start_time = datetime.now()
    
    # 기사 수집
    articles = await collector.collect_all_articles()
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    if articles:
        # Supabase 저장
        save_results = await collector.save_to_supabase(articles)
        
        # JSON 파일 저장
        collector.save_to_json(articles)
        
        # 결과 출력
        collector.display_results(articles, save_results, duration)
    else:
        print("❌ 수집된 기사가 없습니다.")

if __name__ == "__main__":
    asyncio.run(asyncio.run(main()))
