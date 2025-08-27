#!/usr/bin/env python3
"""
Issues 테이블 데이터 보강 스크립트
- Keywords 추출 및 저장
- Bias 분석 및 통계 계산
- Subtitle 개선
"""

import json
import numpy as np
from collections import Counter
from typing import Dict, List, Tuple
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.supabase_manager_unified import UnifiedSupabaseManager
from sklearn.feature_extraction.text import TfidfVectorizer


class IssuesEnricher:
    def __init__(self):
        self.sm = UnifiedSupabaseManager()
        
    def enrich_issues(self):
        """Issues 테이블의 모든 데이터를 보강합니다."""
        print("🔍 Issues 테이블 데이터 보강 시작")
        
        # 1. 기사와 클러스터 정보 로드
        articles, cluster_data = self._load_data()
        if not articles or not cluster_data:
            print("❌ 데이터 로드 실패")
            return False
            
        # 2. 각 클러스터별로 데이터 보강
        for cluster_id, cluster_info in cluster_data.items():
            print(f"\n📊 클러스터 {cluster_id} 처리 중...")
            
            # 클러스터에 속한 기사들
            cluster_articles = [a for a in articles if a['issue_id'] == cluster_id]
            if not cluster_articles:
                continue
                
            # Keywords 추출
            keywords = self._extract_keywords(cluster_articles)
            
            # Bias 분석
            bias_stats = self._analyze_bias(cluster_articles)
            
            # Subtitle 개선
            subtitle = self._generate_subtitle(cluster_articles, keywords)
            
            # Issues 테이블 업데이트
            self._update_issue(cluster_id, keywords, bias_stats, subtitle, cluster_articles)
            
        print("\n✅ Issues 테이블 데이터 보강 완료!")
        return True
        
    def _load_data(self) -> Tuple[List[Dict], Dict]:
        """기사와 클러스터 데이터를 로드합니다."""
        try:
            # 기사 데이터 로드
            articles_result = self.sm.client.table('articles').select('*').execute()
            articles = articles_result.data
            
            # 클러스터 데이터 로드 (ID 1 제외 - 기본 이슈)
            issues_result = self.sm.client.table('issues').select('*').gt('id', 1).execute()
            cluster_data = {issue['id']: issue for issue in issues_result.data}
            
            print(f"📊 {len(articles)}개 기사, {len(cluster_data)}개 클러스터 로드 완료")
            return articles, cluster_data
            
        except Exception as e:
            print(f"❌ 데이터 로드 실패: {e}")
            return [], {}
            
    def _extract_keywords(self, articles: List[Dict], n_top: int = 10) -> List[str]:
        """클러스터의 기사들에서 TF-IDF 키워드를 추출합니다."""
        try:
            # 제목과 내용 결합
            texts = []
            for article in articles:
                title = article.get('title', '')
                content = article.get('content', '')
                if title and content:
                    texts.append(f"{title} {content}")
                    
            if not texts:
                return []
                
            # TF-IDF 벡터화
            cluster_size = len(texts)
            if cluster_size < 3:
                ngram_range = (1, 1)
                min_df = 1
            else:
                ngram_range = (1, 2)
                min_df = 2
                
            vectorizer = TfidfVectorizer(
                ngram_range=ngram_range,
                max_features=5000,
                min_df=min_df,
                stop_words=None
            )
            
            X = vectorizer.fit_transform(texts)
            vocab = np.array(vectorizer.get_feature_names_out())
            
            # 평균 TF-IDF 점수 계산
            tfidf_scores = np.array(X.mean(axis=0)).flatten()
            
            # 상위 키워드 선택
            top_indices = tfidf_scores.argsort()[-n_top:][::-1]
            keywords = vocab[top_indices].tolist()
            
            return keywords
            
        except Exception as e:
            print(f"❌ 키워드 추출 실패: {e}")
            return []
            
    def _analyze_bias(self, articles: List[Dict]) -> Dict:
        """클러스터의 편향성 통계를 분석합니다."""
        try:
            bias_counts = Counter()
            total_articles = len(articles)
            
            for article in articles:
                bias = article.get('bias', 'center')
                bias_counts[bias.lower()] += 1
                
            # 편향성 비율 계산 (기존 스키마에 맞게)
            bias_left_pct = round((bias_counts.get('left', 0) / total_articles) * 100, 1)
            bias_center_pct = round((bias_counts.get('center', 0) / total_articles) * 100, 1)
            bias_right_pct = round((bias_counts.get('right', 0) / total_articles) * 100, 1)
            
            # 주요 편향성 결정
            dominant_bias = bias_counts.most_common(1)[0][0] if bias_counts else 'center'
            
            return {
                'bias_left_pct': bias_left_pct,
                'bias_center_pct': bias_center_pct,
                'bias_right_pct': bias_right_pct,
                'dominant_bias': dominant_bias.title()
            }
            
        except Exception as e:
            print(f"❌ 편향성 분석 실패: {e}")
            return {
                'bias_left_pct': 0.0,
                'bias_center_pct': 100.0,
                'bias_right_pct': 0.0,
                'dominant_bias': 'Center'
            }
            
    def _generate_subtitle(self, articles: List[Dict], keywords: List[str]) -> str:
        """클러스터의 의미있는 부제목을 생성합니다."""
        try:
            if not keywords:
                return f"클러스터 {len(articles)}개 기사"
                
            # 주요 키워드 3개로 부제목 생성
            main_keywords = keywords[:3]
            subtitle = f"{', '.join(main_keywords)} 관련 기사"
            
            return subtitle
            
        except Exception as e:
            print(f"❌ 부제목 생성 실패: {e}")
            return f"클러스터 {len(articles)}개 기사"
            
    def _update_issue(self, cluster_id: int, keywords: List[str], bias_stats: Dict, subtitle: str, articles: List[Dict]):
        """Issues 테이블을 업데이트합니다."""
        try:
            from datetime import datetime
            update_data = {
                'subtitle': subtitle,
                'dominant_bias': bias_stats['dominant_bias'],
                'bias_left_pct': bias_stats['bias_left_pct'],
                'bias_center_pct': bias_stats['bias_center_pct'],
                'bias_right_pct': bias_stats['bias_right_pct'],
                'source_count': len(articles),
                'updated_at': datetime.now().isoformat()
            }
                
            result = self.sm.client.table('issues').update(update_data).eq('id', cluster_id).execute()
            
            if result.data:
                print(f"✅ 클러스터 {cluster_id} 업데이트 완료")
                print(f"   키워드: {len(keywords)}개")
                print(f"   주요 편향: {bias_stats['dominant_bias']}")
                print(f"   부제목: {subtitle}")
            else:
                print(f"❌ 클러스터 {cluster_id} 업데이트 실패")
                
        except Exception as e:
            print(f"❌ 클러스터 {cluster_id} 업데이트 실패: {e}")


def main():
    """메인 실행 함수"""
    print("🚀 Issues 테이블 데이터 보강 시작")
    print("=" * 50)
    
    enricher = IssuesEnricher()
    success = enricher.enrich_issues()
    
    if success:
        print("\n🎉 모든 작업이 성공적으로 완료되었습니다!")
    else:
        print("\n❌ 일부 작업이 실패했습니다.")


if __name__ == "__main__":
    main()
