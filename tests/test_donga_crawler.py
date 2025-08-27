#!/usr/bin/env python3
"""
동아일보 크롤러 직접 테스트
"""

import os
import sys
sys.path.append('.')

from utils.supabase_manager_unified import UnifiedSupabaseManager

def test_donga_crawler():
    """동아일보 크롤러 테스트"""
    manager = UnifiedSupabaseManager()
    
    if not manager.is_connected():
        print("❌ Supabase 연결 실패")
        return
    
    print("✅ Supabase 연결 성공")
    
    # 1. 미디어 아울렛 조회 테스트
    print("\n🔍 1. 동아일보 미디어 아울렛 조회")
    try:
        outlet = manager.get_media_outlet("동아일보")
        if outlet:
            print(f"✅ 동아일보: ID={outlet.get('id')}, Bias={outlet.get('bias')}")
        else:
            print("❌ 동아일보를 찾을 수 없음")
            return
    except Exception as e:
        print(f"❌ 미디어 아울렛 조회 실패: {e}")
        return
    
    # 2. 이슈 ID 조회 테스트
    print("\n🔍 2. 이슈 ID 조회")
    try:
        issue_id = manager.get_random_issue_id()
        if issue_id:
            print(f"✅ 이슈 ID: {issue_id}")
        else:
            print("❌ 이슈 ID를 찾을 수 없음")
            return
    except Exception as e:
        print(f"❌ 이슈 ID 조회 실패: {e}")
        return
    
    # 3. 테스트 기사 삽입 (동아일보 형식으로)
    print("\n🔍 3. 동아일보 형식 테스트 기사 삽입")
    try:
        test_article = {
            'issue_id': issue_id,
            'media_id': outlet['id'],
            'title': '동아일보 테스트 기사',
            'url': 'https://test.com/donga1',
            'content': '이것은 동아일보 테스트 기사입니다.',
            'bias': outlet['bias'],
            'published_at': '2025-08-23T00:00:00Z'  # ISO 형식 문자열
        }
        
        result = manager.insert_article(test_article)
        if result:
            print("✅ 동아일보 형식 기사 삽입 성공")
            
            # 삽입된 기사 확인
            check_result = manager.client.table('articles').select('*').eq('url', 'https://test.com/donga1').execute()
            if check_result.data:
                print(f"   삽입된 기사 ID: {check_result.data[0].get('id')}")
                
                # 테스트 기사 삭제
                delete_result = manager.client.table('articles').delete().eq('url', 'https://test.com/donga1').execute()
                print("   테스트 기사 삭제 완료")
        else:
            print("❌ 동아일보 형식 기사 삽입 실패")
            
    except Exception as e:
        print(f"❌ 동아일보 형식 기사 삽입 중 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_donga_crawler()

