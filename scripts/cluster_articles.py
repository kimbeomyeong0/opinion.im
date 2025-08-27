#!/usr/bin/env python3
"""
기사 임베딩 클러스터링 및 이슈 생성 스크립트
- Supabase embeddings 테이블에서 임베딩 데이터를 직접 로드
- HDBSCAN으로 클러스터링
- 클러스터별로 issues 테이블에 새 row 생성
- 해당 클러스터의 기사들의 issue_id 업데이트
- GPT-4o-mini로 클러스터별 제목, 부제목, 요약 생성
- bias_summaries, common_points, media_summaries 테이블에 GPT 생성 데이터 저장
"""

import sys
import os
import json
import logging
import argparse
import random
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pandas as pd
    import numpy as np
    import umap
    import hdbscan
    from sklearn.preprocessing import StandardScaler
except ImportError as e:
    print(f"❌ 필요한 라이브러리가 설치되지 않았습니다: {e}")
    print("다음 명령어로 설치해주세요:")
    print("pip install pandas umap-learn hdbscan scikit-learn")
    sys.exit(1)

try:
    from openai import OpenAI
except ImportError:
    print("OpenAI 패키지가 설치되지 않았습니다. 'pip install openai'를 실행해주세요.")
    sys.exit(1)

try:
    from utils.supabase_manager_unified import UnifiedSupabaseManager
except ImportError:
    from supabase_manager_unified import UnifiedSupabaseManager

class ArticleClusterer:
    """기사 임베딩 클러스터링 클래스"""
    
    def __init__(self):
        self.supabase = UnifiedSupabaseManager()
        self.logger = logging.getLogger(__name__)
        
        # OpenAI 클라이언트 초기화
        self.openai_client = self._init_openai_client()
        
        # 클러스터링 파라미터 (품질 개선)
        self.umap_params = {
            'n_neighbors': 10,       # 20 → 10으로 감소 (더 지역적 구조 포착)
            'min_dist': 0.1,         # 0.05 → 0.1로 증가 (클러스터 간 거리 증가)
            'n_components': 30,      # 100 → 30으로 감소 (차원 과부하 방지)
            'metric': 'cosine',
            'random_state': 42
        }
        
        self.hdbscan_params = {
            'min_cluster_size': 3,  # 5 → 3으로 더 완화 (매우 작은 클러스터 허용)
            'min_samples': 1,        # 2 → 1로 더 완화 (노이즈 필터링 최소화)
            'metric': 'euclidean',
            'cluster_selection_method': 'eom'
        }
        
        # 통계 정보
        self.stats = {
            'total_articles': 0,
            'clusters_created': 0,
            'articles_updated': 0,
            'noise_articles': 0,
            'gpt_success': 0,
            'gpt_failed': 0,
            'bias_summaries_created': 0,
            'common_points_created': 0,
            'media_summaries_created': 0,
            'start_time': None,
            'end_time': None
        }
    
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
    
    def load_embeddings_from_supabase(self) -> pd.DataFrame:
        """Supabase embeddings 테이블에서 임베딩 데이터 로드"""
        try:
            print("📁 Supabase embeddings 테이블에서 데이터를 로드하는 중...")
            
            # embeddings 테이블 조회
            print("  🔍 embeddings 테이블 조회 중...")
            embeddings_result = self.supabase.client.table('embeddings').select('article_id, embedding').execute()
            if not embeddings_result.data:
                raise ValueError("embeddings 테이블에 데이터가 없습니다.")
            
            print(f"  ✅ embeddings 테이블: {len(embeddings_result.data)}개 행 조회")
            
            # articles 테이블 조회
            print("  🔍 articles 테이블 조회 중...")
            articles_result = self.supabase.client.table('articles').select('id, title, bias, media_id').execute()
            if not articles_result.data:
                raise ValueError("articles 테이블에 데이터가 없습니다.")
            
            print(f"  ✅ articles 테이블: {len(articles_result.data)}개 행 조회")
            
            # 데이터 병합
            print("  🔄 데이터 병합 중...")
            embeddings_df = pd.DataFrame(embeddings_result.data)
            articles_df = pd.DataFrame(articles_result.data)
            
            # 조인
            df = embeddings_df.merge(articles_df, left_on='article_id', right_on='id', how='inner')
            df = df.drop('article_id', axis=1)  # 중복 컬럼 제거
            
            print(f"  ✅ JOIN 완료: {len(df)}개 행")
            
            # 필수 컬럼 확인
            required_columns = ['id', 'embedding', 'title', 'bias', 'media_id']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                raise ValueError(f"필수 컬럼이 누락되었습니다: {missing_columns}")
            
            # embedding을 numpy 배열로 변환 (문자열 파싱)
            def parse_embedding(embedding_str):
                try:
                    # 문자열에서 숫자만 추출하여 numpy 배열로 변환
                    if isinstance(embedding_str, str):
                        # 문자열에서 숫자 부분만 추출
                        import re
                        numbers = re.findall(r'-?\d+\.?\d*', embedding_str)
                        # 차원이 너무 작으면 건너뛰기
                        if len(numbers) < 1000:
                            print(f"⚠️ 임베딩 차원이 너무 작음: {len(numbers)}")
                            return None
                        return np.array([float(num) for num in numbers])
                    else:
                        return np.array(embedding_str)
                except Exception as e:
                    print(f"⚠️ 임베딩 파싱 실패: {e}")
                    return None
            
            df['embedding'] = df['embedding'].apply(parse_embedding)
            
            # 파싱 실패한 행 제거
            df = df.dropna(subset=['embedding'])
            print(f"  ✅ 파싱 완료: {len(df)}개 행 (실패 제거 후)")
            
            # 임베딩 배열을 2D numpy 배열로 변환 (차원 통일)
            embeddings_list = df['embedding'].tolist()
            
            # 모든 임베딩을 동일한 차원으로 맞춤 (가장 작은 차원 기준)
            min_dim = min(len(emb) for emb in embeddings_list)
            print(f"  📏 최소 차원: {min_dim}")
            
            # 모든 임베딩을 동일한 차원으로 자르기
            embeddings_unified = []
            for i, emb in enumerate(embeddings_list):
                if len(emb) >= min_dim:
                    embeddings_unified.append(emb[:min_dim])
                else:
                    print(f"⚠️ 차원이 너무 작은 임베딩 제외 (행 {i}): {len(emb)}")
            
            print(f"  🔢 통일된 임베딩 수: {len(embeddings_unified)}")
            
            # numpy 배열로 변환
            try:
                embeddings_array = np.array(embeddings_unified)
                print(f"  ✅ numpy 배열 변환 완료: {embeddings_array.shape}")
            except Exception as e:
                print(f"❌ numpy 배열 변환 실패: {e}")
                # 첫 번째 임베딩의 구조 확인
                if embeddings_unified:
                    print(f"  🔍 첫 번째 임베딩 타입: {type(embeddings_unified[0])}")
                    print(f"  🔍 첫 번째 임베딩 길이: {len(embeddings_unified[0])}")
                    if len(embeddings_unified[0]) > 0:
                        print(f"  🔍 첫 번째 임베딩 첫 요소 타입: {type(embeddings_unified[0][0])}")
                raise
            
            # 중복 제거
            df = df.drop_duplicates(subset=['id'])
            
            # embedding 컬럼을 numpy 배열로 변환
            df['embedding'] = embeddings_array
            
            self.stats['total_articles'] = len(df)
            print(f"✅ {len(df)}개 기사 임베딩 로드 완료")
            
            return df
            
        except Exception as e:
            self.logger.error(f"Supabase에서 임베딩 데이터 로드 실패: {str(e)}")
            raise
    
    def reduce_dimensions(self, embeddings: np.ndarray) -> np.ndarray:
        """UMAP으로 차원 축소"""
        try:
            # embeddings가 numpy 배열인지 확인
            if not isinstance(embeddings, np.ndarray):
                print(f"⚠️ embeddings 타입 변환: {type(embeddings)} → numpy.ndarray")
                embeddings = np.array(embeddings)
            
            print(f"🔍 embeddings 타입: {type(embeddings)}")
            print(f"🔍 embeddings shape: {embeddings.shape}")
            print(f"🔍 embeddings dtype: {embeddings.dtype}")
            
            if len(embeddings.shape) < 2:
                print(f"⚠️ embeddings가 1차원입니다. reshape 필요")
                embeddings = embeddings.reshape(-1, 1)
                print(f"🔍 reshape 후 shape: {embeddings.shape}")
            
            print(f"🔄 UMAP으로 차원 축소 중... ({embeddings.shape[1]} → {self.umap_params['n_components']})")
            
            # 표준화
            scaler = StandardScaler()
            embeddings_scaled = scaler.fit_transform(embeddings)
            
            # UMAP 적용
            reducer = umap.UMAP(**self.umap_params)
            embeddings_reduced = reducer.fit_transform(embeddings_scaled)
            
            print(f"✅ 차원 축소 완료: {embeddings_reduced.shape}")
            return embeddings_reduced
            
        except Exception as e:
            self.logger.error(f"차원 축소 실패: {str(e)}")
            raise
    
    def cluster_articles(self, embeddings_reduced: np.ndarray) -> np.ndarray:
        """HDBSCAN으로 클러스터링"""
        try:
            print("🔍 HDBSCAN으로 클러스터링 중...")
            
            # HDBSCAN 적용
            clusterer = hdbscan.HDBSCAN(**self.hdbscan_params)
            cluster_labels = clusterer.fit_predict(embeddings_reduced)
            
            # 클러스터 통계
            unique_labels = np.unique(cluster_labels)
            n_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)
            noise_count = np.sum(cluster_labels == -1)
            
            print(f"✅ 클러스터링 완료: {n_clusters}개 클러스터 생성")
            print(f"📊 클러스터 레이블: {unique_labels}")
            print(f"📊 노이즈 기사 수: {noise_count}개")
            
            # 클러스터 품질 평가
            self.evaluate_clustering_quality(embeddings_reduced, cluster_labels)
            
            return cluster_labels
            
        except Exception as e:
            self.logger.error(f"클러스터링 실패: {str(e)}")
            raise
    
    def evaluate_clustering_quality(self, embeddings_reduced: np.ndarray, cluster_labels: np.ndarray):
        """클러스터링 품질 평가"""
        try:
            print("📊 클러스터링 품질 평가 중...")
            
            # 노이즈가 아닌 클러스터만 필터링
            valid_mask = cluster_labels != -1
            if np.sum(valid_mask) == 0:
                print("⚠️ 유효한 클러스터가 없습니다.")
                return
            
            valid_embeddings = embeddings_reduced[valid_mask]
            valid_labels = cluster_labels[valid_mask]
            
            # 클러스터별 크기 분석
            unique_labels, counts = np.unique(valid_labels, return_counts=True)
            print(f"📏 클러스터별 크기:")
            for label, count in zip(unique_labels, counts):
                print(f"  클러스터 {label}: {count}개 기사")
            
            # 클러스터 간 거리 분석
            if len(unique_labels) > 1:
                from sklearn.metrics import silhouette_score
                try:
                    silhouette_avg = silhouette_score(valid_embeddings, valid_labels)
                    print(f"🎯 실루엣 점수: {silhouette_avg:.3f}")
                    if silhouette_avg > 0.5:
                        print("  ✅ 좋은 클러스터링 품질")
                    elif silhouette_avg > 0.25:
                        print("  ⚠️ 보통 클러스터링 품질")
                    else:
                        print("  ❌ 낮은 클러스터링 품질")
                except Exception as e:
                    print(f"⚠️ 실루엣 점수 계산 실패: {e}")
            
            # 클러스터 수가 너무 적으면 경고
            if len(unique_labels) < 8:
                print("⚠️ 클러스터 수가 너무 적습니다. 파라미터 조정이 필요할 수 있습니다.")
                print("  💡 제안: min_cluster_size를 더 줄이거나, min_samples를 줄여보세요")
                print("  💡 제안: UMAP n_neighbors를 늘리거나, min_dist를 줄여보세요")
            elif len(unique_labels) > 50:
                print("⚠️ 클러스터 수가 너무 많습니다. 파라미터 조정이 필요할 수 있습니다.")
                print("  💡 제안: min_cluster_size를 늘리거나, min_samples를 늘려보세요")
                print("  💡 제안: UMAP n_neighbors를 줄이거나, min_dist를 늘려보세요")
            else:
                print(f"✅ 적절한 클러스터 수: {len(unique_labels)}개")
                
        except Exception as e:
            print(f"⚠️ 클러스터링 품질 평가 실패: {e}")
    
    def analyze_clusters(self, df: pd.DataFrame, cluster_labels: np.ndarray) -> Dict:
        """클러스터 분석 및 요약 생성"""
        try:
            print("📊 클러스터 분석 중...")
            
            # 클러스터 레이블 추가
            df['cluster'] = cluster_labels
            
            # 클러스터별 분석
            clusters_summary = {}
            
            for cluster_id in sorted(df['cluster'].unique()):
                if cluster_id == -1:  # 노이즈
                    self.stats['noise_articles'] = len(df[df['cluster'] == cluster_id])
                    continue
                
                cluster_articles = df[df['cluster'] == cluster_id]
                cluster_size = len(cluster_articles)
                
                # bias 분포 계산
                bias_counts = cluster_articles['bias'].value_counts()
                total_articles = len(cluster_articles)
                
                bias_left_pct = (bias_counts.get('left', 0) / total_articles) * 100
                bias_center_pct = (bias_counts.get('center', 0) / total_articles) * 100
                bias_right_pct = (bias_counts.get('right', 0) / total_articles) * 100
                
                # dominant bias 결정
                dominant_bias = bias_counts.idxmax() if len(bias_counts) > 0 else 'unknown'
                
                # 대표 제목 (첫 번째 기사)
                representative_title = cluster_articles.iloc[0]['title']
                
                # 기사 제목 샘플링 (최대 5개)
                sample_titles = cluster_articles['title'].sample(
                    min(5, len(cluster_articles)), 
                    random_state=42
                ).tolist()
                
                # bias별 기사 그룹화
                bias_groups = {}
                for bias in ['left', 'center', 'right']:
                    bias_articles = cluster_articles[cluster_articles['bias'] == bias]
                    if len(bias_articles) > 0:
                        bias_groups[bias] = bias_articles['title'].tolist()
                
                # 언론사별 기사 그룹화
                media_groups = {}
                for media_id in cluster_articles['media_id'].unique():
                    media_articles = cluster_articles[cluster_articles['media_id'] == media_id]
                    if len(media_articles) > 0:
                        media_groups[media_id] = media_articles['title'].tolist()
                
                clusters_summary[cluster_id] = {
                    'size': cluster_size,
                    'title': representative_title,
                    'sample_titles': sample_titles,
                    'all_titles': cluster_articles['title'].tolist(),
                    'bias_groups': bias_groups,
                    'media_groups': media_groups,
                    'bias_left_pct': round(bias_left_pct, 1),
                    'bias_center_pct': round(bias_center_pct, 1),
                    'bias_right_pct': round(bias_right_pct, 1),
                    'dominant_bias': dominant_bias,
                    'articles': cluster_articles
                }
            
            self.stats['clusters_created'] = len(clusters_summary)
            print(f"✅ {len(clusters_summary)}개 클러스터 분석 완료")
            
            return clusters_summary
            
        except Exception as e:
            self.logger.error(f"클러스터 분석 실패: {str(e)}")
            raise
    
    def generate_gpt_content(self, cluster_id: int, summary: Dict) -> Dict[str, str]:
        """GPT-4o-mini로 클러스터별 제목, 부제목, 요약 생성"""
        if not self.openai_client:
            # OpenAI 클라이언트가 없으면 fallback
            return {
                'title': summary['title'],
                'subtitle': f"클러스터 {cluster_id}: {summary['size']}개 기사",
                'summary': f"이 클러스터는 {summary['size']}개의 기사로 구성되어 있으며, 주요 bias는 {summary['dominant_bias']}입니다."
            }
        
        try:
            # 기사 제목들을 하나의 문자열로 결합
            titles_text = "\n".join([f"- {title}" for title in summary['sample_titles']])
            
            # bias 정보 추가
            bias_info = f"\n\nBias 분포: Left {summary['bias_left_pct']}%, Center {summary['bias_center_pct']}%, Right {summary['bias_right_pct']}%"
            dominant_bias_info = f"\n주요 Bias: {summary['dominant_bias']}"
            
            # 프롬프트 템플릿
            title_prompt = f"""다음 기사 제목들을 종합해 간결한 한 줄 대표 제목을 작성해줘.

{titles_text}{bias_info}{dominant_bias_info}

제목만 작성하고 다른 설명은 하지 마세요."""

            subtitle_prompt = f"""이 이슈를 보조 설명하는 짧은 부제목을 작성해줘.

{titles_text}{bias_info}{dominant_bias_info}

부제목만 작성하고 다른 설명은 하지 마세요."""

            summary_prompt = f"""해당 기사들을 종합해 3~4문장으로 요약을 작성해줘.

{titles_text}{bias_info}{dominant_bias_info}

요약만 작성하고 다른 설명은 하지 마세요."""

            # GPT 호출
            print(f"🤖 클러스터 {cluster_id}: GPT로 제목/부제목/요약 생성 중...")
            
            # 제목 생성
            title_response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": title_prompt}],
                max_tokens=100,
                temperature=0.7
            )
            generated_title = title_response.choices[0].message.content.strip()
            
            # 부제목 생성
            subtitle_response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": subtitle_prompt}],
                max_tokens=150,
                temperature=0.7
            )
            generated_subtitle = subtitle_response.choices[0].message.content.strip()
            
            # 요약 생성
            summary_response = self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": summary_prompt}],
                max_tokens=300,
                temperature=0.7
            )
            generated_summary = summary_response.choices[0].message.content.strip()
            
            self.stats['gpt_success'] += 1
            
            return {
                'title': generated_title,
                'subtitle': generated_subtitle,
                'summary': generated_summary
            }
            
        except Exception as e:
            self.logger.error(f"GPT 생성 실패 (클러스터 {cluster_id}): {str(e)}")
            self.stats['gpt_failed'] += 1
            
            # fallback 반환
            return {
                'title': summary['title'],
                'subtitle': f"클러스터 {cluster_id}: {summary['size']}개 기사",
                'summary': f"이 클러스터는 {summary['size']}개의 기사로 구성되어 있으며, 주요 bias는 {summary['dominant_bias']}입니다."
            }
    
    def generate_bias_summaries(self, cluster_id: int, issue_id: str, summary: Dict) -> List[Dict]:
        """각 bias 그룹별로 GPT로 요약 생성"""
        bias_summaries = []
        
        for bias in ['left', 'center', 'right']:
            if bias not in summary['bias_groups'] or len(summary['bias_groups'][bias]) == 0:
                continue
            
            bias_titles = summary['bias_groups'][bias]
            titles_text = "\n".join([f"- {title}" for title in bias_titles])
            
            if not self.openai_client:
                # fallback
                bias_summary = f"{bias} 성향 언론의 시각: {len(bias_titles)}개 기사로 구성"
            else:
                try:
                    prompt = f"""다음 기사 제목들을 요약해서 {bias} 성향 언론이 바라본 시각을 3~4문장으로 정리해줘.

{titles_text}

{bias} 성향 언론의 시각만 요약하고 다른 설명은 하지 마세요."""
                    
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=200,
                        temperature=0.7
                    )
                    bias_summary = response.choices[0].message.content.strip()
                    
                except Exception as e:
                    self.logger.error(f"Bias 요약 GPT 생성 실패 (클러스터 {cluster_id}, {bias}): {str(e)}")
                    bias_summary = f"{bias} 성향 언론의 시각: {len(bias_titles)}개 기사로 구성"
            
            bias_summaries.append({
                'issue_id': issue_id,
                'bias': bias,
                'summary': bias_summary
            })
        
        return bias_summaries
    
    def generate_common_points(self, cluster_id: int, issue_id: str, summary: Dict) -> List[Dict]:
        """클러스터 내 모든 기사 제목을 GPT에 넣고 공통 포인트 3개 생성"""
        all_titles = summary['all_titles']
        titles_text = "\n".join([f"- {title}" for title in all_titles])
        
        if not self.openai_client:
            # fallback
            common_points = [
                f"공통 포인트 1: {all_titles[0][:50]}...",
                f"공통 포인트 2: {all_titles[1][:50]}..." if len(all_titles) > 1 else "공통 포인트 2: 기사 내용 분석",
                f"공통 포인트 3: {all_titles[2][:50]}..." if len(all_titles) > 2 else "공통 포인트 3: 이슈 요약"
            ]
        else:
            try:
                prompt = f"""다음 기사들이 공통적으로 강조하는 핵심 포인트를 3개 bullet point로 뽑아줘.

{titles_text}

3개의 핵심 포인트만 작성하고 다른 설명은 하지 마세요. 각 포인트는 한 문장으로 작성해주세요."""
                
                response = self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300,
                    temperature=0.7
                )
                
                content = response.choices[0].message.content.strip()
                # bullet point들을 분리
                lines = [line.strip() for line in content.split('\n') if line.strip()]
                common_points = []
                
                for line in lines:
                    # bullet point 기호 제거
                    point = line.lstrip('•-*').strip()
                    if point:
                        common_points.append(point)
                
                # 3개로 맞추기
                while len(common_points) < 3:
                    common_points.append(f"공통 포인트 {len(common_points) + 1}: 기사 내용 분석")
                common_points = common_points[:3]
                
            except Exception as e:
                self.logger.error(f"공통 포인트 GPT 생성 실패 (클러스터 {cluster_id}): {str(e)}")
                common_points = [
                    f"공통 포인트 1: {all_titles[0][:50]}...",
                    f"공통 포인트 2: {all_titles[1][:50]}..." if len(all_titles) > 1 else "공통 포인트 2: 기사 내용 분석",
                    f"공통 포인트 3: {all_titles[2][:50]}..." if len(all_titles) > 2 else "공통 포인트 3: 이슈 요약"
                ]
        
        return [{'issue_id': issue_id, 'point': point} for point in common_points]
    
    def generate_media_summaries(self, cluster_id: int, issue_id: str, summary: Dict) -> List[Dict]:
        """각 언론사별로 GPT로 요약 생성"""
        media_summaries = []
        
        for media_id, titles in summary['media_groups'].items():
            if len(titles) == 0:
                continue
            
            titles_text = "\n".join([f"- {title}" for title in titles])
            
            if not self.openai_client:
                # fallback
                media_summary = f"언론사 {media_id}의 시각: {len(titles)}개 기사로 구성"
            else:
                try:
                    prompt = f"""다음은 언론사 {media_id}가 보도한 기사들이다. 이 언론사의 시각을 2~3문장으로 요약해줘.

{titles_text}

언론사 {media_id}의 시각만 요약하고 다른 설명은 하지 마세요."""
                    
                    response = self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{"role": "user", "content": prompt}],
                        max_tokens=200,
                        temperature=0.7
                    )
                    media_summary = response.choices[0].message.content.strip()
                    
                except Exception as e:
                    self.logger.error(f"언론사 요약 GPT 생성 실패 (클러스터 {cluster_id}, 언론사 {media_id}): {str(e)}")
                    media_summary = f"언론사 {media_id}의 시각: {len(titles)}개 기사로 구성"
            
            media_summaries.append({
                'issue_id': issue_id,
                'media_id': media_id,
                'summary': media_summary
            })
        
        return media_summaries
    
    def create_issues(self, clusters_summary: Dict) -> Dict[int, str]:
        """클러스터별로 issues 테이블에 새 row 생성"""
        try:
            print("💾 issues 테이블에 클러스터 저장 중...")
            
            cluster_issue_ids = {}
            
            for cluster_id, summary in clusters_summary.items():
                # GPT로 제목, 부제목, 요약 생성
                gpt_content = self.generate_gpt_content(cluster_id, summary)
                
                # 콘솔에 GPT 생성 결과 출력
                print(f"\n📋 클러스터 {cluster_id} GPT 생성 결과:")
                print(f"  🏷️ 제목: {gpt_content['title']}")
                print(f"  📝 부제목: {gpt_content['subtitle']}")
                print(f"  📄 요약: {gpt_content['summary']}")
                print("-" * 50)
                
                # issues 테이블에 insert
                issue_data = {
                    'title': gpt_content['title'],
                    'subtitle': gpt_content['subtitle'],
                    'summary': gpt_content['summary'],
                    'bias_left_pct': summary['bias_left_pct'],
                    'bias_center_pct': summary['bias_center_pct'],
                    'bias_right_pct': summary['bias_right_pct'],
                    'dominant_bias': summary['dominant_bias'],
                    'source_count': summary['size']
                }
                
                result = self.supabase.client.table('issues').insert(issue_data).execute()
                
                if result.data and len(result.data) > 0:
                    issue_id = result.data[0]['id']
                    cluster_issue_ids[cluster_id] = issue_id
                    print(f"✅ 클러스터 {cluster_id}: issue ID {issue_id} 생성")
                    
                    # 추가 테이블 데이터 생성
                    self._create_additional_tables(cluster_id, issue_id, summary)
                else:
                    print(f"❌ 클러스터 {cluster_id}: issue 생성 실패")
            
            print(f"✅ {len(cluster_issue_ids)}개 issue 생성 완료")
            return cluster_issue_ids
            
        except Exception as e:
            self.logger.error(f"issues 생성 실패: {str(e)}")
            raise
    
    def _create_additional_tables(self, cluster_id: int, issue_id: str, summary: Dict):
        """추가 테이블들(bias_summaries, common_points, media_summaries)에 데이터 생성"""
        try:
            print(f"🔄 클러스터 {cluster_id}: 추가 테이블 데이터 생성 중...")
            
            # 1. bias_summaries 생성
            bias_summaries = self.generate_bias_summaries(cluster_id, issue_id, summary)
            if bias_summaries:
                result = self.supabase.client.table('bias_summaries').insert(bias_summaries).execute()
                if result.data:
                    self.stats['bias_summaries_created'] += len(result.data)
                    print(f"  ✅ bias_summaries: {len(result.data)}개 생성")
                else:
                    print(f"  ❌ bias_summaries 생성 실패")
            
            # 2. common_points 생성
            common_points = self.generate_common_points(cluster_id, issue_id, summary)
            if common_points:
                result = self.supabase.client.table('common_points').insert(common_points).execute()
                if result.data:
                    self.stats['common_points_created'] += len(result.data)
                    print(f"  ✅ common_points: {len(result.data)}개 생성")
                else:
                    print(f"  ❌ common_points 생성 실패")
            
            # 3. media_summaries 생성
            media_summaries = self.generate_media_summaries(cluster_id, issue_id, summary)
            if media_summaries:
                result = self.supabase.client.table('media_summaries').insert(media_summaries).execute()
                if result.data:
                    self.stats['media_summaries_created'] += len(result.data)
                    print(f"  ✅ media_summaries: {len(result.data)}개 생성")
                else:
                    print(f"  ❌ media_summaries 생성 실패")
            
            print(f"  ✅ 클러스터 {cluster_id} 추가 테이블 생성 완료")
            
        except Exception as e:
            self.logger.error(f"추가 테이블 생성 실패 (클러스터 {cluster_id}): {str(e)}")
            print(f"  ❌ 클러스터 {cluster_id} 추가 테이블 생성 실패: {str(e)}")
    
    def update_articles_issue_id(self, clusters_summary: Dict, cluster_issue_ids: Dict[int, str]) -> None:
        """클러스터에 속한 기사들의 issue_id 업데이트"""
        try:
            print("🔄 기사들의 issue_id 업데이트 중...")
            
            total_updated = 0
            
            for cluster_id, summary in clusters_summary.items():
                if cluster_id not in cluster_issue_ids:
                    continue
                
                issue_id = cluster_issue_ids[cluster_id]
                article_ids = summary['articles']['id'].tolist()
                
                # articles 테이블 업데이트
                for article_id in article_ids:
                    result = self.supabase.client.table('articles').update({
                        'issue_id': issue_id
                    }).eq('id', article_id).execute()
                    
                    if result.data:
                        total_updated += 1
                    else:
                        print(f"⚠️ 기사 ID {article_id} 업데이트 실패")
            
            self.stats['articles_updated'] = total_updated
            print(f"✅ {total_updated}개 기사 issue_id 업데이트 완료")
            
        except Exception as e:
            self.logger.error(f"기사 issue_id 업데이트 실패: {str(e)}")
            raise
    
    def display_results(self, clusters_summary: Dict):
        """클러스터링 결과 출력"""
        print("\n🎉 클러스터링 완료!")
        print("=" * 60)
        
        # 클러스터별 요약
        print(f"📊 총 클러스터 수: {len(clusters_summary)}개")
        print(f"📊 총 기사 수: {self.stats['total_articles']}개")
        print(f"📊 노이즈 기사 수: {self.stats['noise_articles']}개")
        print(f"📊 클러스터 생성: {self.stats['clusters_created']}개")
        print(f"📊 기사 업데이트: {self.stats['articles_updated']}개")
        print(f"📊 GPT 성공: {self.stats['gpt_success']}개")
        print(f"📊 GPT 실패: {self.stats['gpt_failed']}개")
        print(f"📊 Bias 요약 생성: {self.stats['bias_summaries_created']}개")
        print(f"📊 공통 포인트 생성: {self.stats['common_points_created']}개")
        print(f"📊 언론사 요약 생성: {self.stats['media_summaries_created']}개")
        
        # 소요 시간
        if self.stats['start_time'] and self.stats['end_time']:
            duration = self.stats['end_time'] - self.stats['start_time']
            print(f"⏱️ 소요 시간: {str(duration).split('.')[0]}")
        
        print("\n📋 클러스터별 상세 정보:")
        print("-" * 60)
        
        for cluster_id, summary in sorted(clusters_summary.items()):
            print(f"클러스터 {cluster_id}:")
            print(f"  📰 기사 수: {summary['size']}개")
            print(f"  🏷️ 대표 제목: {summary['title'][:50]}...")
            print(f"  ⚖️ Bias 분포: L({summary['bias_left_pct']}%) C({summary['bias_center_pct']}%) R({summary['bias_right_pct']}%)")
            print(f"  🎯 주요 Bias: {summary['dominant_bias']}")
            print()
        
        print("=" * 60)
    
    def run_clustering(self) -> bool:
        """전체 클러스터링 프로세스 실행"""
        try:
            # 시작 시간 기록
            self.stats['start_time'] = datetime.now()
            
            print("🚀 OPINION.IM 기사 클러스터링 시작")
            print("=" * 60)
            
            # 1. Supabase에서 임베딩 데이터 로드
            df = self.load_embeddings_from_supabase()
            
            # 2. 차원 축소
            embeddings_array = df['embedding'].values  # pandas Series에서 numpy 배열 추출
            embeddings_reduced = self.reduce_dimensions(embeddings_array)
            
            # 3. 클러스터링
            cluster_labels = self.cluster_articles(embeddings_reduced)
            
            # 4. 클러스터 분석
            clusters_summary = self.analyze_clusters(df, cluster_labels)
            
            # 5. issues 테이블에 저장 (GPT 생성 포함)
            cluster_issue_ids = self.create_issues(clusters_summary)
            
            # 6. 기사들의 issue_id 업데이트
            self.update_articles_issue_id(clusters_summary, cluster_issue_ids)
            
            # 7. 결과 출력
            self.display_results(clusters_summary)
            
            # 종료 시간 기록
            self.stats['end_time'] = datetime.now()
            
            return True
            
        except Exception as e:
            self.logger.error(f"클러스터링 프로세스 실패: {str(e)}")
            print(f"💥 클러스터링 실패: {str(e)}")
            return False


def main():
    """메인 실행 함수"""
    try:
        # 클러스터링 실행
        clusterer = ArticleClusterer()
        success = clusterer.run_clustering()
        
        if success:
            print("\n✅ 클러스터링이 성공적으로 완료되었습니다!")
        else:
            print("\n❌ 클러스터링 중 오류가 발생했습니다.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 예상치 못한 오류가 발생했습니다: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
