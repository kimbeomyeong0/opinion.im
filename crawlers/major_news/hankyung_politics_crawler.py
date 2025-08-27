#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
한국경제 정치 전체 페이지 크롤러
- 목표: 한국경제 정치 전체 페이지에서 최신 기사 100개 수집
- URL: https://www.hankyung.com/all-news-politics
- 방식: 페이지네이션 기반 (page=1~5)
- 중복 제거: URL 기준
- 데이터 품질: 제목, 링크, 날짜, 본문
- 안정성: 3단계 fallback 전략
- 저장: Supabase articles 테이블
- 속도: 20초 내외
"""
import sys
import os
import requests
from bs4 import BeautifulSoup
import time
import re
from tqdm import tqdm
from typing import List, Dict, Optional, Set
from datetime import datetime
import logging

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.supabase_manager_unified import UnifiedSupabaseManager

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 상수 정의
BASE_URL = "https://www.hankyung.com/all-news-politics"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

class HankyungPoliticsCrawler:
    """한국경제 정치 전체 페이지 크롤러"""
    
    def __init__(self, max_articles: int = 100):
        self.max_articles = max_articles
        self.articles = []
        self.seen_urls: Set[str] = set()
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        
        # Supabase 매니저 초기화
        self.supabase_manager = UnifiedSupabaseManager()
        
        # 성능 최적화 설정
        self.adaptive_delay = 0.3
        self.min_delay = 0.1
        self.max_delay = 1.0
        
        # 에러 카운터
        self.network_errors = 0
        self.parsing_errors = 0
        
        # 한국경제는 중도 성향
        self.media_name = "한국경제"
        self.media_bias = "center"
    
    def clean_text(self, text: str) -> str:
        """본문 텍스트 후처리"""
        if not text:
            return ""
            
        # 불필요한 문구 제거
        text = re.sub(r"ⓒ\s*한국경제.*", "", text)  # 저작권 문구
        text = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "", text)  # 이메일 제거
        text = re.sub(r"기자\s*:.*?(?:\n|$)", "", text, flags=re.MULTILINE)  # 기자 정보
        text = re.sub(r"편집\s*:.*?(?:\n|$)", "", text, flags=re.MULTILINE)  # 편집 정보
        
        # 광고 관련 문구 제거
        text = re.sub(r"(광고|sponsored|advertisement).*?(?:\n|$)", "", text, flags=re.MULTILINE | re.IGNORECASE)
        
        # 빈 줄 정리
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)
    
    def parse_article_content(self, url: str) -> str:
        """기사 본문 가져오기 (3단계 fallback)"""
        try:
            # 1단계: 기본 선택자로 본문 추출
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 기본 컨테이너 찾기
            container = soup.select_one("div.article-body#articletxt")
            if container:
                # br 기준으로 문단 분리
                content = container.decode_contents()
                paragraphs = content.split("<br>")
                
                clean_paragraphs = []
                for p in paragraphs:
                    if p.strip():
                        # HTML 태그 제거하고 텍스트만 추출
                        clean_p = BeautifulSoup(p, "html.parser").get_text(" ", strip=True)
                        if clean_p and len(clean_p) > 10:  # 너무 짧은 텍스트 제외
                            clean_paragraphs.append(clean_p)
                
                if clean_paragraphs:
                    result = "\n".join(clean_paragraphs)
                    return self.clean_text(result)
            
            # 2단계: 대안 선택자들 시도
            fallback_selectors = [
                ".article-body",
                ".article-content", 
                ".content",
                "article",
                ".article_body"
            ]
            
            for selector in fallback_selectors:
                container = soup.select_one(selector)
                if container:
                    text = container.get_text("\n", strip=True)
                    if text and len(text) > 100:  # 의미있는 본문인지 확인
                        return self.clean_text(text)
            
            # 3단계: 모든 p 태그에서 추출
            all_paragraphs = soup.find_all('p')
            if all_paragraphs:
                paragraphs_text = []
                for p in all_paragraphs:
                    text = p.get_text(strip=True)
                    if text and len(text) > 20:  # 너무 짧은 텍스트 제외
                        paragraphs_text.append(text)
                
                if paragraphs_text:
                    result = "\n".join(paragraphs_text)
                    return self.clean_text(result)
            
            return "[본문을 찾을 수 없습니다]"
            
        except requests.RequestException as e:
            self.network_errors += 1
            return f"[네트워크 오류] {str(e)}"
        except Exception as e:
            self.parsing_errors += 1
            return f"[본문 수집 실패] {str(e)}"
    
    def crawl_page(self, page: int) -> List[Dict]:
        """특정 페이지에서 기사 정보 수집"""
        articles = []
        url = f"{BASE_URL}?page={page}"
        
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            
            # 기사 리스트 찾기
            news_items = soup.select("div.allnews-wrap div.allnews-panel ul.allnews-list li")
            if not news_items:
                return articles
            
            for item in news_items:
                try:
                    # 제목과 링크 추출
                    title_elem = item.select_one("h2.news-tit a")
                    date_elem = item.select_one("p.txt-date")
                    
                    if not title_elem:
                        continue
                    
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get("href", "")
                    
                    # 링크가 상대 경로인 경우 절대 경로로 변환
                    if link and not link.startswith("http"):
                        link = "https://www.hankyung.com" + link
                    
                    # 중복 확인
                    if link in self.seen_urls:
                        continue
                    
                    # 날짜 추출
                    date = date_elem.get_text(strip=True) if date_elem else ""
                    
                    # 고유 ID 추출 (data-aid 속성)
                    join_key = item.get("data-aid", "")
                    if not join_key:
                        # URL에서 기사 ID 추출
                        join_key_match = re.search(r"/article/(\d+)", link)
                        if join_key_match:
                            join_key = join_key_match.group(1)
                        else:
                            join_key = str(hash(link))  # 최후 수단
                    
                    # 본문 수집
                    body = self.parse_article_content(link)
                    
                    # 기사 정보 구성
                    article = {
                        "title": title,
                        "url": link,
                        "published_at": date,
                        "content": body,
                        "join_key": join_key,
                        "crawled_at": datetime.now().isoformat()
                    }
                    
                    articles.append(article)
                    self.seen_urls.add(link)
                    
                except Exception as e:
                    self.parsing_errors += 1
                    logger.warning(f"기사 파싱 오류: {str(e)}")
                    continue
            
            return articles
            
        except requests.RequestException as e:
            self.network_errors += 1
            logger.error(f"페이지 {page} 요청 오류: {str(e)}")
            return articles
        except Exception as e:
            self.parsing_errors += 1
            logger.error(f"페이지 {page} 파싱 오류: {str(e)}")
            return articles
    
    def crawl_hankyung(self) -> List[Dict]:
        """한국경제 정치 전체 페이지 크롤링 메인 함수"""
        page = 1
        max_pages = 10  # 최대 10페이지까지 시도
        start_time = time.time()
        
        print(f"🚀 한국경제 정치 전체 페이지 크롤링 시작")
        print(f"📅 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 목표: {self.max_articles}개 기사")
        print(f"📰 대상 URL: {BASE_URL}")
        
        with tqdm(total=self.max_articles, desc="크롤링 진행", unit="기사") as pbar:
            while len(self.articles) < self.max_articles and page <= max_pages:
                print(f"\n📄 페이지 {page} 처리 중... (현재: {len(self.articles)}개)")
                
                # 페이지 크롤링
                page_articles = self.crawl_page(page)
                
                if not page_articles:
                    print(f"⚠️  페이지 {page}에서 기사를 찾을 수 없습니다.")
                    # 3단계 fallback: 남은 개수 채우기 시도
                    if len(self.articles) < self.max_articles:
                        remaining = self.max_articles - len(self.articles)
                        print(f"🔄 남은 {remaining}개 기사를 위한 추가 수집 시도...")
                        
                        # 추가 페이지들 시도
                        for extra_page in range(page + 1, page + 5):
                            extra_articles = self.crawl_page(extra_page)
                            if extra_articles:
                                for article in extra_articles:
                                    if len(self.articles) >= self.max_articles:
                                        break
                                    if article["url"] not in self.seen_urls:
                                        self.articles.append(article)
                                        self.seen_urls.add(article["url"])
                                        pbar.update(1)
                            time.sleep(self.adaptive_delay)
                    
                    break
                
                # 새 기사 추가
                new_count = 0
                for article in page_articles:
                    if len(self.articles) >= self.max_articles:
                        break
                    
                    self.articles.append(article)
                    new_count += 1
                    pbar.update(1)
                
                print(f"✅ 페이지 {page}: {new_count}개 새 기사 수집 (총 {len(self.articles)}개)")
                
                # 100개 달성 시 즉시 중단
                if len(self.articles) >= self.max_articles:
                    print(f"🎯 목표 기사 수({self.max_articles}개) 달성! 크롤링 중단")
                    break
                
                # 성공적인 크롤링으로 딜레이 조정
                self.adjust_delay(True)
                
                page += 1
                time.sleep(self.adaptive_delay)
        
        # 결과 저장 (메인에서 처리하므로 여기서는 제거)
        # self.save_to_supabase()
        
        # 성능 분석
        end_time = time.time()
        duration = end_time - start_time
        
        # display_results는 메인에서 처리하므로 여기서는 제거
        # self.display_results(duration)
        return self.articles
    
    def adjust_delay(self, success: bool):
        """적응형 딜레이 조정"""
        if success:
            # 성공 시 딜레이 감소
            self.adaptive_delay = max(self.adaptive_delay * 0.9, self.min_delay)
        else:
            # 실패 시 딜레이 증가
            self.adaptive_delay = min(self.adaptive_delay * 1.2, self.max_delay)
    
    async def save_to_database(self, articles: List[Dict]):
        """데이터베이스에 기사 저장"""
        if not articles:
            print("저장할 기사가 없습니다.")
            return
        
        print(f"\n💾 {len(articles)}개 기사를 데이터베이스에 저장 중...")
        
        successful_saves = 0
        failed_saves = 0
        
        for article in articles:
            try:
                # 새로 만든 저장 메서드 사용
                if await self.save_article_to_supabase(article):
                    successful_saves += 1
                else:
                    failed_saves += 1
                    
            except Exception as e:
                failed_saves += 1
                print(f"❌ 기사 저장 실패: {article['title']} - {str(e)}")
        
        print(f"\n📊 Supabase 저장 결과:")
        print(f"  • 성공: {successful_saves}개")
        print(f"  • 실패: {failed_saves}개")
        print(f"  • 총 기사: {len(articles)}개")
        
        if successful_saves > 0:
            print(f"✅ {successful_saves}개 기사가 Supabase에 성공적으로 저장되었습니다!")
    
    def display_results(self, duration: float):
        """크롤링 결과 표시"""
        print(f"\n{'='*60}")
        print(f"      한국경제 정치 전체 페이지 크롤링 완료!      ")
        print(f"{'='*60}")
        print(f"📊 수집 결과:")
        print(f"  • 총 기사 수: {len(self.articles)}개")
        print(f"  • 소요 시간: {duration:.1f}초")
        
        # 0으로 나누는 문제 해결
        if duration > 0:
            print(f"  • 평균 속도: {len(self.articles)/duration:.1f} 기사/초")
        else:
            print(f"  • 평균 속도: 계산 불가")
            
        print(f"  • 네트워크 오류: {self.network_errors}회")
        print(f"  • 파싱 오류: {self.parsing_errors}회")
        
        if duration > 25:
            print(f"⚠️  목표 시간(25초)을 초과했습니다: {duration:.1f}초")
        else:
            print(f"✅ 목표 시간 내 완료: {duration:.1f}초")
        
        if len(self.articles) >= self.max_articles:
            print(f"✅ 목표 기사 수({self.max_articles}개) 달성!")
        else:
            print(f"⚠️  목표 기사 수({self.max_articles}개) 미달성: {len(self.articles)}개")
    
    async def collect_all_articles(self) -> List[Dict]:
        """모든 기사 수집 (비동기 인터페이스)"""
        try:
            return self.crawl_hankyung()
        except KeyboardInterrupt:
            print("\n⚠️  사용자에 의해 중단되었습니다.")
            return self.articles
        except Exception as e:
            print(f"\n❌ 크롤러 실행 중 오류 발생: {str(e)}")
            logger.error(f"크롤러 오류: {str(e)}", exc_info=True)
            return self.articles

    def run(self):
        """크롤러 실행"""
        try:
            return self.crawl_hankyung()
        except KeyboardInterrupt:
            print("\n⚠️  사용자에 의해 중단되었습니다.")
            return self.articles
        except Exception as e:
            print(f"\n❌ 크롤러 실행 중 오류 발생: {str(e)}")
            logger.error(f"크롤러 오류: {str(e)}", exc_info=True)
            return self.articles

    async def create_default_issue(self):
        """기본 이슈를 생성합니다."""
        try:
            # 기존 이슈 확인
            existing = self.supabase_manager.client.table('issues').select('id').eq('id', 1).execute()
            
            if not existing.data:
                # 기본 이슈 생성
                issue_data = {
                    'id': 1,
                    'title': '기본 이슈',
                    'subtitle': '크롤러로 수집된 기사들을 위한 기본 이슈',
                    'summary': '다양한 언론사에서 수집된 정치 관련 기사들을 포함하는 기본 이슈입니다.',
                    'bias_left_pct': 0,
                    'bias_center_pct': 0,
                    'bias_right_pct': 0,
                    'dominant_bias': 'center',
                    'source_count': 0
                }
                
                result = self.supabase_manager.client.table('issues').insert(issue_data).execute()
                logger.info("기본 이슈 생성 성공")
                return True
            else:
                logger.info("기본 이슈가 이미 존재합니다")
                return True
                
        except Exception as e:
            logger.error(f"기본 이슈 생성 실패: {str(e)}")
            return False

    async def save_article_to_supabase(self, article_data: Dict) -> bool:
        """기사를 Supabase에 저장"""
        try:
            # 기본 이슈 생성 확인
            await self.create_default_issue()
            
            # datetime을 문자열로 변환
            published_at = article_data.get('published_at')
            if isinstance(published_at, datetime):
                published_at = published_at.isoformat()
            
            # 기사 데이터 준비
            insert_data = {
                'issue_id': 1,  # 기본 이슈 ID 사용
                'media_id': 4,  # 한경 media_id
                'title': article_data['title'],
                'url': article_data['url'],
                'content': article_data['content'],
                'bias': self.media_bias.lower(),
                'published_at': published_at
            }
            
            # Supabase에 저장
            result = self.supabase_manager.client.table('articles').insert(insert_data).execute()
            
            if result.data:
                logger.info(f"기사 저장 성공: {article_data['title'][:50]}...")
                return True
            else:
                logger.error(f"기사 저장 실패: {article_data['title'][:50]}...")
                return False
                
        except Exception as e:
            logger.error(f"기사 저장 중 오류 발생: {str(e)}")
            return False

async def main():
    """메인 함수"""
    crawler = HankyungPoliticsCrawler(max_articles=100)
    
    # 기사 수집
    articles = await crawler.collect_all_articles()
    
    # 결과 표시
    crawler.display_results(0)  # 시간은 임시로 0으로 설정
    
    # 데이터베이스 저장
    await crawler.save_to_database(articles)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
