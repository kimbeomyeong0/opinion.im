#!/usr/bin/env python3
"""
데이터베이스 문제 진단 스크립트
"""

import os
import sys
sys.path.append('.')

from utils.supabase_manager_unified import UnifiedSupabaseManager

def debug_database():
    """데이터베이스 문제 진단"""
    manager = UnifiedSupabaseManager()
    
    if not manager.is_connected():
        print("❌ Supabase 연결 실패")
        return
    
    print("✅ Supabase 연결 성공")
    
    # 1. articles 테이블 구조 확인
    print("\n🔍 1. articles 테이블 구조 확인")
    try:
        result = manager.client.table('articles').select('*').limit(1).execute()
        if result.data:
            print("✅ articles 테이블에 데이터가 있습니다")
            sample = result.data[0]
            print(f"   샘플 데이터 컬럼: {list(sample.keys())}")
        else:
            print("⚠️ articles 테이블이 비어있습니다")
    except Exception as e:
        print(f"❌ articles 테이블 조회 실패: {e}")
    
    # 2. articles 테이블 스키마 확인
    print("\n🔍 2. articles 테이블 스키마 확인")
    try:
        # RPC를 통해 스키마 정보 조회 시도
        schema_result = manager.client.rpc('get_table_schema', {'table_name': 'articles'}).execute()
        print(f"✅ 스키마 정보: {schema_result.data}")
    except Exception as e:
        print(f"⚠️ 스키마 조회 실패 (정상): {e}")
    
    # 3. media_outlets 테이블 확인
    print("\n🔍 3. media_outlets 테이블 확인")
    try:
        result = manager.client.table('media_outlets').select('*').execute()
        print(f"✅ media_outlets 테이블: {len(result.data)}개 레코드")
        for outlet in result.data[:5]:  # 처음 5개만
            print(f"   ID: {outlet.get('id')}, Name: {outlet.get('name')}, Bias: {outlet.get('bias')}")
    except Exception as e:
        print(f"❌ media_outlets 조회 실패: {e}")
    
    # 4. issues 테이블 확인
    print("\n🔍 4. issues 테이블 확인")
    try:
        result = manager.client.table('issues').select('*').execute()
        print(f"✅ issues 테이블: {len(result.data)}개 레코드")
        if result.data:
            for issue in result.data[:3]:  # 처음 3개만
                print(f"   ID: {issue.get('id')}, Title: {issue.get('title', 'N/A')[:30]}...")
    except Exception as e:
        print(f"❌ issues 조회 실패: {e}")
    
    # 5. 테스트 기사 삽입 시도
    print("\n🔍 5. 테스트 기사 삽입 시도")
    try:
        test_article = {
            'issue_id': 1,  # 첫 번째 이슈 ID 사용
            'media_id': 1,  # 조선일보 ID
            'title': '테스트 기사',
            'url': 'https://test.com/article1',
            'content': '이것은 테스트 기사입니다.',
            'bias': 'Right',
            'published_at': '2025-08-23T00:00:00Z'
        }
        
        result = manager.insert_article(test_article)
        if result:
            print("✅ 테스트 기사 삽입 성공")
            
            # 삽입된 기사 확인
            check_result = manager.client.table('articles').select('*').eq('url', 'https://test.com/article1').execute()
            if check_result.data:
                print(f"   삽입된 기사 ID: {check_result.data[0].get('id')}")
                
                # 테스트 기사 삭제
                delete_result = manager.client.table('articles').delete().eq('url', 'https://test.com/article1').execute()
                print("   테스트 기사 삭제 완료")
        else:
            print("❌ 테스트 기사 삽입 실패")
            
    except Exception as e:
        print(f"❌ 테스트 기사 삽입 중 오류: {e}")
    
    # 6. RLS 정책 확인
    print("\n🔍 6. RLS 정책 확인")
    print("   RLS 정책은 Supabase 대시보드에서 확인해야 합니다.")
    print("   다음 정책들이 필요합니다:")
    print("   - articles 테이블: INSERT, SELECT, UPDATE, DELETE")
    print("   - media_outlets 테이블: SELECT")
    print("   - issues 테이블: SELECT")

if __name__ == "__main__":
    debug_database()

