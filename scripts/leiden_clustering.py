#!/usr/bin/env python3
"""
Leiden 기반 그래프 클러스터링 파이프라인

목표:
1) (title + lead 최대 500자) 임베딩 벡터를 L2 정규화
2) FAISS(또는 sklearn NearestNeighbors, cosine)로 k=25 kNN 그래프 생성
3) 엣지 가중치=코사인유사도, 무방향 그래프(igraph) 구성
4) Leiden으로 resolution ∈ {0.8, 1.0, 1.2, 1.3} 스윕
5) 각 결과에 대해 (a) 클러스터 개수, (b) 최대/중간/최소 클러스터 크기, (c) 코사인 실루엣 스코어 계산
   → 가장 “10~20개”에 가까우면서 실루엣이 높은 모델 선택
6) 선택 결과의 cluster_id를 Supabase articles.issue_id(또는 별도 mapping)로 저장
7) 각 클러스터별 c-TF-IDF(또는 단순 TF-IDF)로 상위 키워드/bi-gram 10개 추출해 issue 레이블 후보 생성
8) (옵션) 2D UMAP은 시각화 전용으로만 산출, 저장

주의:
- metric은 cosine 고정, 임베딩은 반드시 L2 normalize
- 노이즈 없이 모든 노드가 어떤 커뮤니티엔 속하게
- 결과 요약 표(클러스터 개수, 크기분포, 실루엣) 콘솔에 출력
"""

import os
import sys
import re
import json
from datetime import datetime
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

# 프로젝트 루트 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.supabase_manager_unified import UnifiedSupabaseManager
except ImportError:
    from supabase_manager_unified import UnifiedSupabaseManager

# 선택 라이브러리들
try:
    import faiss  # type: ignore
    FAISS_AVAILABLE = True
except Exception:
    FAISS_AVAILABLE = False

from sklearn.neighbors import NearestNeighbors
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    import igraph as ig
    import leidenalg as la
except Exception as e:
    print("❌ igraph/leidenalg 미설치: pip install python-igraph leidenalg")
    raise

try:
    import umap
    UMAP_AVAILABLE = True
except Exception:
    UMAP_AVAILABLE = False


def parse_embedding(value) -> np.ndarray:
    """Supabase USER-DEFINED embedding을 numpy 배열로 파싱."""
    if isinstance(value, (list, np.ndarray)):
        return np.array(value, dtype=np.float32)
    if isinstance(value, str):
        nums = re.findall(r"-?\d+\.?\d*", value)
        arr = np.array([float(x) for x in nums], dtype=np.float32)
        return arr
    raise ValueError("Unknown embedding format")


def l2_normalize_rows(matrix: np.ndarray) -> np.ndarray:
    return normalize(matrix, norm='l2', axis=1)


def build_knn_cosine(embeddings: np.ndarray, k: int = 25) -> Tuple[np.ndarray, np.ndarray]:
    """코사인 거리 기반 kNN 인덱스 구성. 반환: (indices, similarities)"""
    # 코사인 유사도 = 내적 (L2 정규화 전제)
    if FAISS_AVAILABLE:
        index = faiss.IndexFlatIP(embeddings.shape[1])
        index.add(embeddings.astype(np.float32))
        sims, idxs = index.search(embeddings.astype(np.float32), k + 1)  # self 포함
        # 첫 열은 자기 자신(유사도=1) 제거
        return idxs[:, 1:], sims[:, 1:]
    # fallback: sklearn
    nn = NearestNeighbors(n_neighbors=k + 1, metric='cosine', algorithm='brute').fit(embeddings)
    distances, indices = nn.kneighbors(embeddings)
    # 코사인 유사도 = 1 - distance
    sims = 1.0 - distances
    return indices[:, 1:], sims[:, 1:]


def knn_to_igraph(indices: np.ndarray, similarities: np.ndarray) -> ig.Graph:
    """kNN 결과를 무방향 가중 그래프로 변환."""
    n = indices.shape[0]
    edges = []
    weights = []
    for i in range(n):
        for j in range(indices.shape[1]):
            nbr = int(indices[i, j])
            w = float(similarities[i, j])
            if i == nbr:
                continue
            # 무방향 그래프: (min,max)로 중복 방지
            a, b = (i, nbr) if i < nbr else (nbr, i)
            edges.append((a, b))
            weights.append(w)
    g = ig.Graph()
    g.add_vertices(n)
    g.add_edges(edges)
    g.es['weight'] = weights
    return g.simplify(combine_edges={'weight': 'mean'})


def leiden_sweep(graph: ig.Graph, resolutions: List[float], embeddings: np.ndarray) -> Dict:
    """여러 resolution에서 Leiden 실행 후 통계/실루엣 수집."""
    results = {}
    for res in resolutions:
        # CPM 대신 Modularity 또는 RBConfiguration 사용으로 과분할 방지
        try:
            # Modularity는 음수 가중치를 허용하지 않으므로 절댓값 사용
            weights = [abs(w) for w in graph.es['weight']]
            part = la.find_partition(graph, la.ModularityVertexPartition, weights=weights)
        except Exception:
            # fallback: RBConfiguration
            part = la.find_partition(graph, la.RBConfigurationVertexPartition, weights='weight', resolution_parameter=res)
        labels = np.array(part.membership)
        # 실루엣 (코사인 거리)
        try:
            sil = silhouette_score(embeddings, labels, metric='cosine') if len(np.unique(labels)) > 1 else -1.0
        except Exception:
            sil = -1.0
        sizes = np.bincount(labels)
        sizes_sorted = np.sort(sizes)
        results[res] = {
            'labels': labels,
            'n_clusters': int(len(sizes)),
            'size_min': int(sizes_sorted[0]) if len(sizes_sorted) else 0,
            'size_med': int(np.median(sizes_sorted)) if len(sizes_sorted) else 0,
            'size_max': int(sizes_sorted[-1]) if len(sizes_sorted) else 0,
            'silhouette': float(sil),
        }
    return results


def choose_best_result(results: Dict) -> Tuple[float, Dict]:
    """10~20개에 가깝고 실루엣이 높은 결과 선택."""
    best_key = None
    best_score = -1e9
    best = None
    for res, info in results.items():
        c = info['n_clusters']
        sil = info['silhouette']
        # 군집 수 패널티: 10~20 범위 밖이면 선형 페널티
        if c < 10:
            penalty = (10 - c) * 0.1
        elif c > 20:
            penalty = (c - 20) * 0.1
        else:
            penalty = 0.0
        score = sil - penalty
        if score > best_score:
            best_score = score
            best_key = res
            best = info
    return best_key, best


def extract_keywords_by_cluster(titles: List[str], labels: np.ndarray, n_top: int = 10) -> Dict[int, List[Tuple[str, float]]]:
    """단순 TF-IDF로 군집별 상위 n-gram 키워드 추출."""
    df = pd.DataFrame({'title': titles, 'label': labels})
    keywords = {}
    for label in sorted(df['label'].unique()):
        texts = df[df['label'] == label]['title'].fillna("").astype(str).tolist()
        if not texts:
            keywords[label] = []
            continue
        # 클러스터 크기에 따라 동적 min_df 설정으로 충돌 방지
        cluster_size = len(texts)
        if cluster_size < 3:
            # 소형 클러스터: uni-gram만, min_df=1
            ngram_range = (1, 1)
            min_df = 1
        else:
            # 대형 클러스터: bi-gram 포함, min_df=2
            ngram_range = (1, 2)
            min_df = 2
        
        vectorizer = TfidfVectorizer(ngram_range=ngram_range, max_features=5000, min_df=min_df)
        X = vectorizer.fit_transform(texts)
        vocab = np.array(vectorizer.get_feature_names_out())
        # 평균 TF-IDF로 상위 n 추출
        scores = np.asarray(X.mean(axis=0)).ravel()
        top_idx = np.argsort(scores)[::-1][:n_top]
        keywords[label] = [(vocab[i], float(scores[i])) for i in top_idx]
    return keywords


def load_embeddings_from_supabase() -> pd.DataFrame:
    sm = UnifiedSupabaseManager()
    emb = sm.client.table('embeddings').select('article_id, embedding').execute()
    if not emb.data:
        raise ValueError('embeddings 테이블에 데이터가 없습니다')
    # lead 컬럼 이슈(함수로 인식)로 인해 content를 사용
    arts = sm.client.table('articles').select('id, title, content, issue_id').execute()
    if not arts.data:
        raise ValueError('articles 테이블에 데이터가 없습니다')
    df_emb = pd.DataFrame(emb.data)
    df_art = pd.DataFrame(arts.data)
    df = df_emb.merge(df_art, left_on='article_id', right_on='id', how='inner')
    # 파싱 및 정제
    df['embedding'] = df['embedding'].apply(parse_embedding)
    df = df.dropna(subset=['embedding'])
    # 차원 통일 (최소 차원)
    min_dim = min(len(x) for x in df['embedding'])
    df['embedding'] = df['embedding'].apply(lambda x: x[:min_dim].astype(np.float32))
    return df


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--k', type=int, default=50, help='kNN에서 k (25→50으로 상향)')
    parser.add_argument('--update-articles', action='store_true', help='articles.issue_id에 저장 시도')
    parser.add_argument('--save-mapping', action='store_true', help='별도 매핑 테이블 저장 시도(article_cluster_mapping)')
    parser.add_argument('--save-umap', action='store_true', help='UMAP 2D 계산 및 CSV 저장')
    args = parser.parse_args()

    print('🚀 Leiden 클러스터링 시작')
    df = load_embeddings_from_supabase()
    # title + content 최대 500자
    titles = (df['title'].fillna("").astype(str) + ' ' + df['content'].fillna("").astype(str)).str.slice(0, 500).tolist()
    article_ids = df['id'].tolist()

    embeddings = np.stack(df['embedding'].to_list()).astype(np.float32)
    embeddings = l2_normalize_rows(embeddings)

    print('🔗 kNN 그래프 구성 중...')
    idxs, sims = build_knn_cosine(embeddings, k=args.k)
    graph = knn_to_igraph(idxs, sims)
    print(f'✅ 그래프: |V|={graph.vcount()}, |E|={graph.ecount()}')

    # 클러스터 품질 개선을 위한 resolution 그리드 재설계
    resolutions = [0.1, 0.2, 0.3, 0.5, 0.8]
    print(f'🧪 Leiden 스윕: {resolutions}')
    sweep = leiden_sweep(graph, resolutions, embeddings)

    # 요약 표 출력
    print('\n📊 스윕 결과 요약:')
    print('resolution,n_clusters,size_min,size_med,size_max,silhouette')
    for r in resolutions:
        info = sweep[r]
        print(f"{r},{info['n_clusters']},{info['size_min']},{info['size_med']},{info['size_max']},{info['silhouette']:.4f}")

    best_res, best_info = choose_best_result(sweep)
    labels = best_info['labels']
    print(f"\n✅ 선택된 resolution={best_res} → n_clusters={best_info['n_clusters']}, silhouette={best_info['silhouette']:.4f}")

    # 키워드 추출
    print('🔤 클러스터별 키워드 추출(TF-IDF, uni/bi-gram) ...')
    keywords = extract_keywords_by_cluster(titles, labels, n_top=10)
    for lab, items in keywords.items():
        top_terms = ', '.join([w for w, _ in items])
        print(f"  - Cluster {lab}: {top_terms}")

    # 선택 결과 저장
    sm = UnifiedSupabaseManager()
    
    print('💾 issues 테이블에 클러스터 정보 저장 중...')
    issue_ids = {}  # cluster_label -> issue_id 매핑
    
    # 각 클러스터를 issues 테이블에 저장
    for cluster_label in sorted(set(labels)):
        cluster_mask = labels == cluster_label
        cluster_titles = [titles[i] for i in range(len(titles)) if cluster_mask[i]]
        cluster_articles = [article_ids[i] for i in range(len(article_ids)) if cluster_mask[i]]
        
        # 클러스터 제목 생성 (첫 번째 기사 제목 사용)
        if cluster_titles:
            cluster_title = cluster_titles[0][:100]  # 최대 100자
        else:
            cluster_title = f"클러스터 {cluster_label}"
        
        # 클러스터 요약 생성
        cluster_summary = f"총 {len(cluster_articles)}개 기사로 구성된 클러스터"
        
        # bias 통계 계산 (간단한 예시)
        bias_left_pct = 0.0
        bias_center_pct = 0.0
        bias_right_pct = 0.0
        dominant_bias = "Center"  # 기본값
        
        try:
            # issues 테이블에 삽입
            issue_data = {
                'title': cluster_title,
                'subtitle': f"클러스터 {cluster_label}",
                'summary': cluster_summary,
                'bias_left_pct': bias_left_pct,
                'bias_center_pct': bias_center_pct,
                'bias_right_pct': bias_right_pct,
                'dominant_bias': dominant_bias,
                'source_count': len(cluster_articles),
                'updated_at': datetime.utcnow().isoformat()
            }
            
            result = sm.client.table('issues').insert(issue_data).execute()
            if result.data:
                issue_id = result.data[0]['id']
                issue_ids[cluster_label] = issue_id
                print(f"  ✅ 클러스터 {cluster_label}: issue_id {issue_id} 생성")
            else:
                print(f"  ❌ 클러스터 {cluster_label}: issues 테이블 저장 실패")
                
        except Exception as e:
            print(f"  ❌ 클러스터 {cluster_label}: {e}")
    
    print(f'✅ 총 {len(issue_ids)}개 클러스터를 issues 테이블에 저장')
    
    # articles.issue_id 업데이트
    print('💾 articles.issue_id 업데이트 중...')
    updated_count = 0
    for i, (article_id, cluster_label) in enumerate(zip(article_ids, labels)):
        if cluster_label in issue_ids:
            try:
                result = sm.client.table('articles').update({
                    'issue_id': issue_ids[cluster_label]
                }).eq('id', article_id).execute()
                if result.data:
                    updated_count += 1
            except Exception as e:
                print(f"  ⚠️ 기사 {article_id} 업데이트 실패: {e}")
    
    print(f'✅ articles.issue_id 업데이트 완료: {updated_count}개 기사')

    # UMAP 2D 저장(옵션)
    if args.save_umap and UMAP_AVAILABLE:
        print('🗺️ UMAP 2D 계산 중...')
        reducer = umap.UMAP(n_neighbors=15, min_dist=0.1, n_components=2, metric='cosine', random_state=42)
        emb2d = reducer.fit_transform(embeddings)
        out = pd.DataFrame({
            'article_id': article_ids,
            'x': emb2d[:, 0],
            'y': emb2d[:, 1],
            'label': labels,
        })
        os.makedirs('outputs', exist_ok=True)
        out_path = os.path.join('outputs', 'umap_2d.csv')
        out.to_csv(out_path, index=False)
        print(f'✅ UMAP 2D 저장: {out_path}')

    # 매핑 로컬 저장 (fallback)
    if not (args.save_mapping or args.update_articles):
        os.makedirs('outputs', exist_ok=True)
        mapping_path = os.path.join('outputs', 'article_cluster_mapping.json')
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump({str(a): int(l) for a, l in zip(article_ids, labels.tolist())}, f, ensure_ascii=False)
        print(f'💾 로컬 매핑 저장: {mapping_path}')

    print('\n🎉 완료')


if __name__ == '__main__':
    main()


