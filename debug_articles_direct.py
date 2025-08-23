#!/usr/bin/env python3
"""
데이터베이스 직접 조회로 문제 파악
"""

import os
import sys
sys.path.append('.')

from utils.supabase_manager_unified import UnifiedSupabaseManager

def debug_articles_direct():
    """데이터베이스에서 직접 기사 조회"""
    manager = UnifiedSupabaseManager()
    
    if not manager.is_connected():
        print("❌ Supabase 연결 실패")
        return
    
    print("✅ Supabase 연결 성공")
    
    # 1. 전체 기사 수 확인
    print("\n🔍 1. 전체 기사 수 확인")
    try:
        result = manager.client.table('articles').select('id', count='exact').execute()
        total_count = result.count or 0
        print(f"📊 articles 테이블 총 기사 수: {total_count:,}개")
    except Exception as e:
        print(f"❌ 기사 수 조회 실패: {e}")
        return
    
    # 2. 문화일보 기사 직접 조회
    print("\n🔍 2. 문화일보 기사 직접 조회 (ID 6)")
    try:
        result = manager.client.table('articles').select('id, title, url, media_id, published_at').eq('media_id', 6).execute()
        if result.data:
            print(f"✅ 문화일보 기사 {len(result.data)}개 발견:")
            for i, article in enumerate(result.data[:5], 1):
                print(f"   {i}. ID: {article.get('id')}, 제목: {article.get('title', 'N/A')[:50]}...")
            if len(result.data) > 5:
                print(f"   ... 외 {len(result.data) - 5}개")
        else:
            print("❌ 문화일보 기사 없음")
    except Exception as e:
        print(f"❌ 문화일보 기사 조회 실패: {e}")
    
    # 3. 프레시안 기사 직접 조회
    print("\n🔍 3. 프레시안 기사 직접 조회 (ID 10)")
    try:
        result = manager.client.table('articles').select('id, title, url, media_id, published_at').eq('media_id', 10).execute()
        if result.data:
            print(f"✅ 프레시안 기사 {len(result.data)}개 발견:")
            for i, article in enumerate(result.data[:5], 1):
                print(f"   {i}. ID: {article.get('id')}, 제목: {article.get('title', 'N/A')[:50]}...")
            if len(result.data) > 5:
                print(f"   ... 외 {len(result.data) - 5}개")
        else:
            print("❌ 프레시안 기사 없음")
    except Exception as e:
        print(f"❌ 프레시안 기사 조회 실패: {e}")
    
    # 4. JTBC 기사 직접 조회
    print("\n🔍 4. JTBC 기사 직접 조회 (ID 13)")
    try:
        result = manager.client.table('articles').select('id, title, url, media_id, published_at').eq('media_id', 13).execute()
        if result.data:
            print(f"✅ JTBC 기사 {len(result.data)}개 발견:")
            for i, article in enumerate(result.data[:5], 1):
                print(f"   {i}. ID: {article.get('id')}, 제목: {article.get('title', 'N/A')[:50]}...")
            if len(result.data) > 5:
                print(f"   ... 외 {len(result.data) - 5}개")
        else:
            print("❌ JTBC 기사 없음")
    except Exception as e:
        print(f"❌ JTBC 기사 조회 실패: {e}")
    
    # 5. 최근 추가된 기사 확인 (ID 기준)
    print("\n🔍 5. 최근 추가된 기사 확인 (ID 기준)")
    try:
        result = manager.client.table('articles').select('id, title, media_id, published_at').order('id', desc=True).limit(10).execute()
        if result.data:
            print("📰 최근 10개 기사:")
            for article in result.data:
                media_id = article.get('media_id')
                media_name = f"ID {media_id}"
                if media_id == 6: media_name = "문화일보"
                elif media_id == 10: media_name = "프레시안"
                elif media_id == 13: media_name = "JTBC"
                print(f"   ID: {article.get('id')}, {media_name}, 제목: {article.get('title', 'N/A')[:40]}...")
        else:
            print("⚠️ 최근 기사가 없습니다")
    except Exception as e:
        print(f"❌ 최근 기사 조회 실패: {e}")
    
    # 6. 특정 URL로 기사 존재 여부 확인
    print("\n🔍 6. 특정 URL로 기사 존재 여부 확인")
    test_urls = [
        "https://www.munhwa.com/news/view.html?no=2025082301039900000001",
        "https://www.pressian.com/pages/articles/2025082210493608439",
        "https://news.jtbc.co.kr/article/article_index.aspx?news_id=NT202508230001"
    ]
    
    for url in test_urls:
        try:
            result = manager.client.table('articles').select('id, title, media_id').eq('url', url).execute()
            if result.data:
                article = result.data[0]
                print(f"✅ URL 존재: {url[:50]}... (ID: {article.get('id')}, 미디어: {article.get('media_id')})")
            else:
                print(f"❌ URL 없음: {url[:50]}...")
        except Exception as e:
            print(f"❌ URL 조회 실패: {url[:50]}... - {e}")

if __name__ == "__main__":
    debug_articles_direct()

