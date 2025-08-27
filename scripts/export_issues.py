#!/usr/bin/env python3
"""
Issues 테이블 JSON 출력 스크립트
- Supabase의 issues 테이블 데이터를 JSON 파일로 출력
- DB와 동시에 JSON 파일로 저장
"""

import sys
import os
import json
from datetime import datetime
from typing import Dict, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.supabase_manager_unified import UnifiedSupabaseManager


class IssuesExporter:
    def __init__(self):
        self.sm = UnifiedSupabaseManager()
        
    def export_issues_to_json(self):
        """Issues 테이블을 JSON 파일로 출력합니다."""
        print("📤 Issues 테이블 JSON 출력 시작")
        
        try:
            # Issues 테이블 데이터 로드
            result = self.sm.client.table('issues').select('*').execute()
            issues = result.data
            
            if not issues:
                print("❌ Issues 데이터가 없습니다.")
                return False
                
            print(f"📊 {len(issues)}개 이슈 데이터 로드 완료")
            
            # JSON 파일명 생성 (타임스탬프 포함)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"outputs/issues_export_{timestamp}.json"
            
            # 디렉토리 생성
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # JSON 파일로 저장
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(issues, f, ensure_ascii=False, indent=2)
                
            print(f"✅ JSON 파일 저장 완료: {filename}")
            
            # 요약 정보 출력
            self._print_summary(issues)
            
            # 최신 파일로도 저장 (덮어쓰기)
            latest_filename = "outputs/issues_latest.json"
            with open(latest_filename, 'w', encoding='utf-8') as f:
                json.dump(issues, f, ensure_ascii=False, indent=2)
                
            print(f"✅ 최신 파일 저장 완료: {latest_filename}")
            
            return True
            
        except Exception as e:
            print(f"❌ JSON 출력 실패: {e}")
            return False
            
    def _print_summary(self, issues: List[Dict]):
        """이슈 데이터 요약을 출력합니다."""
        print("\n📊 Issues 데이터 요약:")
        print("=" * 50)
        
        # 기본 이슈 제외하고 클러스터만
        clusters = [issue for issue in issues if issue['id'] > 1]
        
        print(f"총 이슈 수: {len(issues)}개")
        print(f"클러스터 수: {len(clusters)}개")
        print(f"기본 이슈: 1개")
        
        print("\n🔍 클러스터별 요약:")
        for cluster in clusters:
            cluster_id = cluster['id']
            title = cluster.get('title', '제목 없음')[:50]
            subtitle = cluster.get('subtitle', '부제목 없음')[:50]
            dominant_bias = cluster.get('dominant_bias', '알 수 없음')
            source_count = cluster.get('source_count', 0)
            
            print(f"  클러스터 {cluster_id}: {title}...")
            print(f"    부제목: {subtitle}...")
            print(f"    주요 편향: {dominant_bias}, 기사 수: {source_count}개")
            print()
            
        # 편향성 통계
        bias_counts = {}
        for cluster in clusters:
            bias = cluster.get('dominant_bias', 'Unknown')
            bias_counts[bias] = bias_counts.get(bias, 0) + 1
            
        print("📈 편향성 분포:")
        for bias, count in bias_counts.items():
            print(f"  {bias}: {count}개 클러스터")
            
        # 기사 수 통계
        total_articles = sum(cluster.get('source_count', 0) for cluster in clusters)
        avg_articles = total_articles / len(clusters) if clusters else 0
        
        print(f"\n📰 기사 통계:")
        print(f"  총 기사 수: {total_articles}개")
        print(f"  클러스터당 평균: {avg_articles:.1f}개")
        
        # 가장 큰/작은 클러스터
        if clusters:
            largest_cluster = max(clusters, key=lambda x: x.get('source_count', 0))
            smallest_cluster = min(clusters, key=lambda x: x.get('source_count', 0))
            
            print(f"  가장 큰 클러스터: {largest_cluster['id']} ({largest_cluster.get('source_count', 0)}개)")
            print(f"  가장 작은 클러스터: {smallest_cluster['id']} ({smallest_cluster.get('source_count', 0)}개)")


def main():
    """메인 실행 함수"""
    print("🚀 Issues 테이블 JSON 출력 시작")
    print("=" * 50)
    
    exporter = IssuesExporter()
    success = exporter.export_issues_to_json()
    
    if success:
        print("\n🎉 Issues JSON 출력이 성공적으로 완료되었습니다!")
        print("📁 outputs/ 디렉토리에 JSON 파일이 저장되었습니다.")
    else:
        print("\n❌ Issues JSON 출력이 실패했습니다.")


if __name__ == "__main__":
    main()
