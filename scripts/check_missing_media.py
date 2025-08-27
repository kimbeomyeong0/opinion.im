#!/usr/bin/env python3
"""
미디어 아울렛별 기사 수 확인 및 누락된 언론사 체크
"""

import os
import sys
sys.path.append('.')

from utils.supabase_manager_unified import UnifiedSupabaseManager

def check_missing_media():
    """미디어 아울렛별 기사 수 확인 및 누락된 언론사 체크"""
    manager = UnifiedSupabaseManager()
    
    if not manager.is_connected():
        print("❌ Supabase 연결 실패")
        return
    
    print("✅ Supabase 연결 성공")
    
    # 1. media_outlets 테이블의 모든 언론사 확인
    print("\n🔍 1. media_outlets 테이블의 모든 언론사")
    try:
        result = manager.client.table('media_outlets').select('*').order('id').execute()
        all_media = result.data
        print(f"📰 총 {len(all_media)}개 언론사:")
        for media in all_media:
            print(f"   ID {media['id']:2d}: {media['name']} ({media['bias']})")
    except Exception as e:
        print(f"❌ media_outlets 조회 실패: {e}")
        return
    
    # 2. articles 테이블의 미디어별 기사 수 확인
    print("\n🔍 2. articles 테이블의 미디어별 기사 수")
    try:
        result = manager.client.table('articles').select('media_id').execute()
        if result.data:
            media_counts = {}
            for article in result.data:
                media_id = article.get('media_id')
                media_counts[media_id] = media_counts.get(media_id, 0) + 1
            
            print("📊 미디어별 저장된 기사 수:")
            for media_id in sorted(media_counts.keys()):
                count = media_counts[media_id]
                media_name = next((m['name'] for m in all_media if m['id'] == media_id), f"ID {media_id}")
                print(f"   {media_name:12s}: {count:3d}개")
        else:
            print("⚠️ 기사 데이터가 없습니다")
    except Exception as e:
        print(f"❌ 미디어별 기사 수 조회 실패: {e}")
        return
    
    # 3. 누락된 미디어 확인
    print("\n🔍 3. 누락된 미디어 (기사가 0개인 언론사)")
    try:
        result = manager.client.table('articles').select('media_id').execute()
        if result.data:
            media_with_articles = set(article.get('media_id') for article in result.data)
            missing_media = [media for media in all_media if media['id'] not in media_with_articles]
            
            if missing_media:
                print("❌ 기사가 없는 언론사들:")
                for media in missing_media:
                    print(f"   ID {media['id']:2d}: {media['name']} ({media['bias']})")
            else:
                print("✅ 모든 언론사에 기사가 있습니다!")
        else:
            print("⚠️ 기사 데이터가 없어서 비교할 수 없습니다")
    except Exception as e:
        print(f"❌ 누락된 미디어 확인 실패: {e}")
    
    # 4. 기사 수가 적은 미디어 (10개 미만)
    print("\n🔍 4. 기사 수가 적은 미디어 (10개 미만)")
    try:
        result = manager.client.table('articles').select('media_id').execute()
        if result.data:
            media_counts = {}
            for article in result.data:
                media_id = article.get('media_id')
                media_counts[media_id] = media_counts.get(media_id, 0) + 1
            
            low_count_media = []
            for media in all_media:
                count = media_counts.get(media['id'], 0)
                if count < 10:
                    low_count_media.append((media, count))
            
            if low_count_media:
                print("⚠️ 기사 수가 적은 언론사들:")
                for media, count in sorted(low_count_media, key=lambda x: x[1]):
                    print(f"   {media['name']:12s}: {count:3d}개")
            else:
                print("✅ 모든 언론사가 충분한 기사를 보유하고 있습니다!")
        else:
            print("⚠️ 기사 데이터가 없어서 확인할 수 없습니다")
    except Exception as e:
        print(f"❌ 기사 수가 적은 미디어 확인 실패: {e}")
    
    # 5. 전체 통계
    print("\n🔍 5. 전체 통계")
    try:
        result = manager.client.table('articles').select('id', count='exact').execute()
        total_articles = result.count or 0
        
        result = manager.client.table('articles').select('media_id').execute()
        if result.data:
            media_with_articles = set(article.get('media_id') for article in result.data)
            active_media_count = len(media_with_articles)
            
            print(f"📊 전체 기사 수: {total_articles:,}개")
            print(f"📰 활성 언론사 수: {active_media_count}개 (기사가 있는 언론사)")
            print(f"📰 전체 언론사 수: {len(all_media)}개")
            print(f"📰 비활성 언론사 수: {len(all_media) - active_media_count}개 (기사가 없는 언론사)")
            
            if active_media_count > 0:
                avg_articles = total_articles / active_media_count
                print(f"📰 언론사당 평균 기사 수: {avg_articles:.1f}개")
        else:
            print("⚠️ 기사 데이터가 없어서 통계를 계산할 수 없습니다")
    except Exception as e:
        print(f"❌ 전체 통계 계산 실패: {e}")

if __name__ == "__main__":
    check_missing_media()

