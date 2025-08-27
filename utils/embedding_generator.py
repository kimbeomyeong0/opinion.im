#!/usr/bin/env python3
"""
OpenAI 임베딩 생성 모듈
- Supabase articles 테이블에서 아직 embeddings가 없는 기사를 조회
- OpenAI text-embedding-3-small 모델로 임베딩 생성
- embeddings 테이블에 embedding 컬럼으로 저장
- 중복 방지 및 진행 상황 모니터링
- 429 에러 처리 및 자동 속도 조절
"""

import os
import logging
import random
import time
from typing import List, Dict, Optional, Tuple
from datetime import datetime

try:
    from utils.supabase_manager_unified import UnifiedSupabaseManager
except ImportError:
    from supabase_manager_unified import UnifiedSupabaseManager

try:
    from openai import OpenAI
except ImportError:
    print("OpenAI 패키지가 설치되지 않았습니다. 'pip install openai'를 실행해주세요.")
    exit(1)

class EmbeddingGenerator:
    """OpenAI 임베딩 생성 클래스"""
    
    def __init__(self, limit: Optional[int] = None):
        self.supabase = UnifiedSupabaseManager()
        self.logger = logging.getLogger(__name__)
        self.limit = limit  # 테스트용 기사 개수 제한
        
        # OpenAI 클라이언트 초기화
        self.openai_client = self._init_openai_client()
        
        # 모드별 설정
        if self.limit:  # 테스트 모드
            self.batch_size = 1
            self.base_delay = 1
            print(f"🧪 테스트 모드: batch_size={self.batch_size}, base_delay={self.base_delay}초")
        else:  # 운영 모드
            self.batch_size = 1
            self.base_delay = 2
            print(f"🚀 운영 모드: batch_size={self.batch_size}, base_delay={self.base_delay}초")
        
        # 동적 딜레이 관리
        self.current_delay = self.base_delay
        self.max_delay = 60  # 최대 대기 시간
        
        # 통계 정보
        self.stats = {
            'total_articles': 0,
            'already_embedded': 0,
            'newly_embedded': 0,
            'failed_embeddings': 0,
            'skipped_articles': 0,
            'rate_limit_retries': 0,
            'total_retries': 0,
            'start_time': None,
            'end_time': None,
            'successful_requests': 0,
            'failed_requests': 0
        }
        
        # 에러 추적
        self.failed_article_ids = []  # 실패한 article_id 리스트
        self.skipped_article_ids = []  # 건너뛴 article_id 리스트
        
        # 재시도 설정
        self.max_retries = 10  # 429 에러에 대해서는 무한 재시도 대신 딜레이 조절
    
    def _init_openai_client(self) -> Optional[OpenAI]:
        """OpenAI 클라이언트 초기화"""
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            print("❌ OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
            print("환경 변수에 OpenAI API 키를 설정해주세요.")
            return None
        
        try:
            client = OpenAI(api_key=api_key)
            print("✅ OpenAI 클라이언트 초기화 성공")
            return client
        except Exception as e:
            print(f"❌ OpenAI 클라이언트 초기화 실패: {str(e)}")
            self.logger.error(f"OpenAI 클라이언트 초기화 실패: {str(e)}")
            return None
    
    def embed_articles(self) -> bool:
        """기사 임베딩 메인 함수"""
        if not self.supabase.is_connected():
            print("❌ Supabase에 연결되지 않았습니다.")
            return False
        
        if not self.openai_client:
            print("❌ OpenAI 클라이언트가 초기화되지 않았습니다.")
            return False
        
        try:
            # 시작 시간 기록
            self.stats['start_time'] = datetime.now()
            
            print("🚀 OPINION.IM 기사 임베딩 시작")
            print("=" * 60)
            
            # 1. 임베딩이 필요한 기사 조회
            print("🔍 임베딩이 필요한 기사를 조회하는 중...")
            articles_to_embed = self._get_articles_needing_embedding()
            if not articles_to_embed:
                print("⚠️ 임베딩이 필요한 기사가 없습니다.")
                return True
            
            self.stats['total_articles'] = len(articles_to_embed)
            print(f"📊 임베딩 대상: {len(articles_to_embed)}개 기사")
            
            # 2. 배치 단위로 임베딩 생성 및 저장
            success = self._process_embeddings_in_batches(articles_to_embed)
            
            # 3. 결과 출력
            self._display_results()
            
            return success
            
        except Exception as e:
            self.logger.error(f"임베딩 생성 중 오류 발생: {str(e)}")
            print(f"💥 임베딩 생성 실패: {str(e)}")
            return False
    
    def _get_articles_needing_embedding(self) -> List[Dict]:
        """임베딩이 필요한 기사 조회 (embeddings 테이블에 없는 기사)"""
        try:
            print("  🔍 이미 임베딩된 article_id 조회 중...")
            # 이미 임베딩된 article_id 조회
            existing_embeddings = self.supabase.client.table('embeddings').select('article_id').execute()
            existing_ids = set()
            if existing_embeddings.data:
                existing_ids = {item['article_id'] for item in existing_embeddings.data}
                print(f"  ✅ 기존 임베딩: {len(existing_ids)}개")
            else:
                print("  ✅ 기존 임베딩: 0개")
            
            print("  🔍 articles 테이블에서 기사 조회 중...")
            # 모든 기사 조회 (content가 있는 것만)
            all_articles = self.supabase.client.table('articles').select('id, content, title, media_id, bias, published_at').execute()
            if not all_articles.data:
                print("  ❌ articles 테이블에 데이터가 없습니다.")
                return []
            
            print(f"  ✅ 전체 기사: {len(all_articles.data)}개")
            
            # 임베딩이 필요한 기사만 필터링
            articles_needing_embedding = []
            for article in all_articles.data:
                article_id = article.get('id')
                content = article.get('content', '')
                title = article.get('title', '')
                
                # content가 있고, 아직 임베딩되지 않은 기사만 선택
                if content and article_id not in existing_ids:
                    articles_needing_embedding.append(article)
                elif article_id in existing_ids:
                    self.stats['already_embedded'] += 1
                elif not content:
                    self.stats['skipped_articles'] += 1
                    self.skipped_article_ids.append(article_id)
            
            print(f"  📊 임베딩 필요: {len(articles_needing_embedding)}개")
            print(f"  📊 이미 임베딩됨: {self.stats['already_embedded']}개")
            print(f"  📊 건너뜀: {self.stats['skipped_articles']}개")
            
            # limit 설정이 있다면 제한
            if self.limit and len(articles_needing_embedding) > self.limit:
                articles_needing_embedding = articles_needing_embedding[:self.limit]
                print(f"📊 테스트 실행: {self.limit}개 기사만 임베딩")
            
            return articles_needing_embedding
            
        except Exception as e:
            self.logger.error(f"기사 조회 실패: {str(e)}")
            print(f"❌ 기사 조회 실패: {str(e)}")
            return []
    
    def _process_embeddings_in_batches(self, articles: List[Dict]) -> bool:
        """배치 단위로 임베딩 처리"""
        total_batches = (len(articles) + self.batch_size - 1) // self.batch_size
        
        print(f"📦 총 {total_batches}개 배치로 처리 (배치 크기: {self.batch_size})")
        print("=" * 60)
        
        for i in range(0, len(articles), self.batch_size):
            batch = articles[i:i + self.batch_size]
            batch_num = (i // self.batch_size) + 1
            
            print(f"\n🔄 배치 {batch_num}/{total_batches} 처리 중... ({len(batch)}개 기사)")
            
            # 배치 처리
            batch_success = self._process_batch(batch, batch_num, total_batches)
            if not batch_success:
                print(f"❌ 배치 {batch_num} 처리 실패")
            
            # 배치 간 딜레이 (마지막 배치가 아닌 경우에만)
            if batch_num < total_batches:
                delay = random.uniform(self.current_delay * 0.5, self.current_delay * 1.5)
                if delay > 0:
                    print(f"⏳ {delay:.1f}초 대기 중...")
                    time.sleep(delay)
        
        return True
    
    def _process_batch(self, batch: List[Dict], batch_num: int, total_batches: int) -> bool:
        """배치 단위 임베딩 처리"""
        try:
            embeddings_to_insert = []
            batch_stats = {'success': 0, 'failed': 0}
            
            for idx, article in enumerate(batch, 1):
                article_id = article.get('id')
                content = article.get('content', '')
                title = article.get('title', '')
                
                if not content:
                    self.stats['skipped_articles'] += 1
                    self.skipped_article_ids.append(article_id)
                    print(f"⚠️ 건너뜀: 기사 ID={article_id} (내용 없음)")
                    continue
                
                # 원문 길이와 잘린 길이 계산
                original_length = len(content)
                max_chars = 1000
                truncated_length = min(original_length, max_chars)
                
                # OpenAI 임베딩 생성 (지속적인 재시도)
                embedding = self._generate_embedding_with_persistence(content, title, article_id)
                if embedding:
                    embeddings_to_insert.append({
                        'article_id': article_id,
                        'embedding': embedding,  # 'embedding' 컬럼 사용
                        'created_at': datetime.now().isoformat()
                    })
                    self.stats['newly_embedded'] += 1
                    batch_stats['success'] += 1
                    print(f"✂️ {article_id} → {original_length}자 → {truncated_length}자 → 임베딩 성공")
                    
                    # 성공 시 딜레이 초기화
                    self.current_delay = self.base_delay
                else:
                    self.stats['failed_embeddings'] += 1
                    self.failed_article_ids.append(article_id)  # 실패한 article_id 저장
                    batch_stats['failed'] += 1
                    print(f"✂️ {article_id} → {original_length}자 → {truncated_length}자 → 임베딩 실패")
            
            # 배치로 embeddings 테이블에 저장
            if embeddings_to_insert:
                save_success = self._insert_embeddings_batch(embeddings_to_insert)
                if save_success:
                    print(f"💾 데이터베이스 저장 완료: {len(embeddings_to_insert)}개 임베딩")
                else:
                    print(f"❌ 데이터베이스 저장 실패")
            
            # 배치 완료 출력
            print(f"✅ {len(batch)}개 기사 임베딩 완료 (성공: {batch_stats['success']}, 실패: {batch_stats['failed']})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"배치 처리 실패: {str(e)}")
            return False
    
    def _generate_embedding_with_persistence(self, content: str, title: str, article_id: int) -> Optional[List[float]]:
        """지속적인 재시도로 OpenAI 임베딩 생성 (429 에러 시 딜레이 조절)"""
        max_attempts = self.max_retries
        
        for attempt in range(1, max_attempts + 1):
            try:
                # 제목과 본문을 결합하여 임베딩 생성
                combined_text = f"제목: {title}\n\n본문: {content}"
                
                # 텍스트 길이 제한
                max_chars = 1000
                if len(combined_text) > max_chars:
                    combined_text = combined_text[:max_chars]
                
                response = self.openai_client.embeddings.create(
                    model="text-embedding-3-small",
                    input=combined_text
                )
                
                # 성공 시 통계 업데이트
                self.stats['successful_requests'] += 1
                return response.data[0].embedding
                
            except Exception as e:
                error_message = str(e)
                self.stats['failed_requests'] += 1
                
                # 429 에러 (Rate Limit) 처리
                if "429" in error_message or "Too Many Requests" in error_message:
                    self.stats['rate_limit_retries'] += 1
                    self.stats['total_retries'] += 1
                    
                    # 딜레이를 2배로 증가 (최대 60초)
                    self.current_delay = min(self.current_delay * 2, self.max_delay)
                    
                    print(f"⚠️ Rate Limit: {self.current_delay:.0f}초 대기 후 재시도 (시도 {attempt}/{max_attempts})")
                    time.sleep(self.current_delay)
                    continue
                
                # 기타 에러 - 로그 남기고 다음 기사로
                else:
                    print(f"❌ API 에러 (기사 ID={article_id}): {error_message}")
                    self.logger.error(f"기사 ID {article_id} 임베딩 실패: {error_message}")
                    return None
        
        # 최대 시도 횟수 초과
        print(f"❌ 최대 시도 횟수 초과: 기사 ID={article_id}")
        return None
    
    def _insert_embeddings_batch(self, embeddings: List[Dict]) -> bool:
        """embeddings 테이블에 배치 삽입"""
        try:
            result = self.supabase.client.table('embeddings').insert(embeddings).execute()
            return result.data is not None
        except Exception as e:
            self.logger.error(f"임베딩 저장 실패: {str(e)}")
            print(f"❌ 임베딩 저장 실패: {str(e)}")
            return False
    
    def _display_results(self):
        """임베딩 결과 출력"""
        # 종료 시간 기록
        self.stats['end_time'] = datetime.now()
        
        # 소요 시간 계산
        if self.stats['start_time'] and self.stats['end_time']:
            duration = self.stats['end_time'] - self.stats['start_time']
            duration_str = str(duration).split('.')[0]  # 마이크로초 제거
        else:
            duration_str = "알 수 없음"
        
        print("\n🎉 임베딩 생성 완료!")
        print("=" * 60)
        
        # 최종 요약
        print(f"📊 총 기사 수: {self.stats['total_articles']}개 (처리 대상)")
        print(f"✅ 성공: {self.stats['newly_embedded']}개 (새로 생성됨)")
        print(f"❌ 실패: {self.stats['failed_embeddings']}개 (재시도 후 실패)")
        print(f"⚠️ 이미 존재: {self.stats['already_embedded']}개 (기존 임베딩)")
        print(f"⚠️ 건너뜀: {self.stats['skipped_articles']}개 (내용 없음)")
        print(f"⏱️ 소요 시간: {duration_str}")
        
        # 처리 속도 계산
        if self.stats['total_articles'] > 0 and duration:
            total_seconds = duration.total_seconds()
            articles_per_minute = (self.stats['newly_embedded'] / total_seconds) * 60
            print(f"🚀 처리 속도: {articles_per_minute:.1f}개/분")
        
        # 상세 통계
        if self.stats['rate_limit_retries'] > 0:
            print(f"⚠️ Rate Limit 재시도: {self.stats['rate_limit_retries']}회")
        if self.stats['total_retries'] > 0:
            print(f"⚠️ 총 재시도: {self.stats['total_retries']}회")
        
        # 성공률 계산
        if self.stats['total_articles'] > 0:
            success_rate = (self.stats['newly_embedded'] / self.stats['total_articles']) * 100
            print(f"\n🎯 임베딩 성공률: {success_rate:.1f}%")
        
        # 실패한 기사 ID 출력
        if self.failed_article_ids:
            print(f"\n❌ 실패한 기사 ID 목록 ({len(self.failed_article_ids)}개):")
            for i, article_id in enumerate(self.failed_article_ids[:10]):  # 최대 10개만 출력
                print(f"  {i+1}. {article_id}")
            if len(self.failed_article_ids) > 10:
                print(f"  ... 및 {len(self.failed_article_ids) - 10}개 더")
        
        # 건너뛴 기사 ID 출력
        if self.skipped_article_ids:
            print(f"\n⚠️ 건너뛴 기사 ID 목록 ({len(self.skipped_article_ids)}개):")
            for i, article_id in enumerate(self.skipped_article_ids[:10]):  # 최대 10개만 출력
                print(f"  {i+1}. {article_id}")
            if len(self.skipped_article_ids) > 10:
                print(f"  ... 및 {len(self.skipped_article_ids) - 10}개 더")
        
        print("=" * 60)
    
    def get_embedding_stats(self) -> Dict:
        """임베딩 통계 정보 반환"""
        stats = self.stats.copy()
        stats['failed_article_ids'] = self.failed_article_ids
        stats['skipped_article_ids'] = self.skipped_article_ids
        return stats


def main():
    """메인 실행 함수"""
    generator = EmbeddingGenerator()
    success = generator.embed_articles()
    
    if success:
        print("\n✅ 임베딩 생성이 성공적으로 완료되었습니다!")
        stats = generator.get_embedding_stats()
        print(f"📊 새로 생성된 임베딩: {stats['newly_embedded']}개")
        print(f"📊 실패한 임베딩: {stats['failed_embeddings']}개")
        print(f"📊 실패한 기사 ID: {len(stats['failed_article_ids'])}개")
    else:
        print("\n❌ 임베딩 생성 중 오류가 발생했습니다.")


if __name__ == "__main__":
    main()
