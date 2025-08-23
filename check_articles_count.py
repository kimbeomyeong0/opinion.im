#!/usr/bin/env python3
"""
articles 테이블 상태 확인 스크립트
"""

import os
import sys
sys.path.append('.')

from utils.supabase_manager_unified import UnifiedSupabaseManager

def check_articles_table():
    """articles 테이블 상태 확인"""
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
    
    # 2. 언론사별 기사 수 확인 (언론사 이름 포함)
    print("\n🔍 2. 언론사별 기사 수 확인")
    try:
        # 먼저 media_id가 null이 아닌 기사 수 확인
        media_id_check = manager.client.table('articles').select('media_id').not_.is_('media_id', 'null').execute()
        non_null_media_count = len(media_id_check.data) if media_id_check.data else 0
        print(f"📊 media_id가 null이 아닌 기사 수: {non_null_media_count:,}개")
        
        # 미디어 아울렛 정보와 함께 조회
        result = manager.client.table('articles').select(
            'media_id, media_outlets(name, bias)'
        ).execute()
        
        if result.data:
            media_counts = {}
            media_details = {}
            null_media_count = 0
            joined_count = 0
            
            for article in result.data:
                media_id = article.get('media_id')
                if media_id is None:
                    null_media_count += 1
                    continue
                
                joined_count += 1
                media_info = article.get('media_outlets', {})
                media_name = media_info.get('name', f'Unknown-{media_id}') if media_info else f'Unknown-{media_id}'
                media_bias = media_info.get('bias', 'Unknown') if media_info else 'Unknown'
                
                if media_id not in media_counts:
                    media_counts[media_id] = 0
                    media_details[media_id] = {'name': media_name, 'bias': media_bias}
                
                media_counts[media_id] += 1
            
            print(f"📊 조인 쿼리 결과 기사 수: {joined_count:,}개")
            
            print("📰 언론사별 기사 수:")
            total_by_media = 0
            for media_id, count in sorted(media_counts.items()):
                details = media_details[media_id]
                print(f"   {details['name']} (ID: {media_id}, 편향성: {details['bias']}): {count:,}개")
                total_by_media += count
            
            if null_media_count > 0:
                print(f"   📝 media_id가 null인 기사: {null_media_count:,}개")
            
            print(f"\n📊 언론사별 총합: {total_by_media:,}개")
            print(f"📊 media_id null 기사: {null_media_count:,}개")
            print(f"📊 조인 결과 총합: {total_by_media + null_media_count:,}개")
            print(f"📊 media_id non-null 기사: {non_null_media_count:,}개")
            
            if non_null_media_count != joined_count:
                print(f"⚠️ 경고: media_id non-null 기사({non_null_media_count:,})와 조인 결과({joined_count:,})가 다릅니다")
                print(f"   차이: {non_null_media_count - joined_count:,}개")
            
            if (total_by_media + null_media_count) != total_count:
                print(f"⚠️ 경고: 계산된 합계({total_by_media + null_media_count:,})와 전체 기사 수({total_count:,})가 다릅니다")
                print(f"   차이: {total_count - (total_by_media + null_media_count):,}개")
                
                # media_id가 null인 기사들의 샘플 확인
                print(f"\n🔍 media_id가 null인 기사들 분석:")
                try:
                    # 먼저 media_id가 null인 기사 수를 정확히 확인
                    null_count_query = manager.client.table('articles').select('id', count='exact').is_('media_id', 'null').execute()
                    actual_null_count = null_count_query.count or 0
                    print(f"📊 실제 media_id가 null인 기사 수: {actual_null_count:,}개")
                    
                    if actual_null_count > 0:
                        # media_id가 null인 기사들의 샘플 확인
                        null_media_articles = manager.client.table('articles').select(
                            'id, title, published_at, issue_id, bias'
                        ).is_('media_id', 'null').limit(5).execute()
                        
                        if null_media_articles.data:
                            print("📰 media_id가 null인 기사 샘플 (최근 5개):")
                            for article in null_media_articles.data:
                                title = article.get('title', 'N/A')
                                if len(title) > 60:
                                    title = title[:60] + "..."
                                print(f"   ID: {article.get('id')}, 제목: {title}")
                                print(f"      발행일: {article.get('published_at', 'N/A')}, 이슈: {article.get('issue_id', 'N/A')}, 편향성: {article.get('bias', 'N/A')}")
                        else:
                            print("⚠️ media_id가 null인 기사 샘플을 가져올 수 없습니다")
                    else:
                        print("📊 media_id가 null인 기사가 없습니다")
                        
                except Exception as e:
                    print(f"❌ media_id가 null인 기사 분석 실패: {e}")
                    # 대체 방법으로 시도
                    try:
                        print("🔄 대체 방법으로 media_id가 null인 기사 확인 중...")
                        all_articles = manager.client.table('articles').select('id, media_id').execute()
                        if all_articles.data:
                            null_count = sum(1 for article in all_articles.data if article.get('media_id') is None)
                            print(f"📊 대체 방법으로 확인한 media_id null 기사 수: {null_count:,}개")
                    except Exception as e2:
                        print(f"❌ 대체 방법도 실패: {e2}")
        else:
            print("⚠️ 기사 데이터가 없습니다")
    except Exception as e:
        print(f"❌ 언론사별 기사 수 조회 실패: {e}")
        # 대체 방법으로 시도
        try:
            result = manager.client.table('articles').select('media_id').execute()
            if result.data:
                media_counts = {}
                null_media_count = 0
                for article in result.data:
                    media_id = article.get('media_id')
                    if media_id is None:
                        null_media_count += 1
                    else:
                        media_counts[media_id] = media_counts.get(media_id, 0) + 1
                
                print("📰 언론사별 기사 수 (미디어 ID만):")
                for media_id, count in sorted(media_counts.items()):
                    print(f"   미디어 ID {media_id}: {count:,}개")
                
                if null_media_count > 0:
                    print(f"   📝 media_id가 null인 기사: {null_media_count:,}개")
            else:
                print("⚠️ 기사 데이터가 없습니다")
        except Exception as e2:
            print(f"❌ 대체 방법도 실패: {e2}")
    
    # 3. 최근 기사 샘플 확인
    print("\n🔍 3. 최근 기사 샘플 확인")
    try:
        result = manager.client.table('articles').select(
            'id, title, media_id, published_at, media_outlets(name)'
        ).order('id', desc=True).limit(5).execute()
        
        if result.data:
            print("📰 최근 5개 기사:")
            for article in result.data:
                media_name = "Unknown"
                if article.get('media_outlets'):
                    media_name = article['media_outlets'].get('name', 'Unknown')
                
                title = article.get('title', 'N/A')
                if len(title) > 50:
                    title = title[:50] + "..."
                
                print(f"   ID: {article.get('id')}, 제목: {title}, 언론사: {media_name}")
        else:
            print("⚠️ 최근 기사가 없습니다")
    except Exception as e:
        print(f"❌ 최근 기사 조회 실패: {e}")
    
    # 4. 이슈별 기사 수 확인
    print("\n🔍 4. 이슈별 기사 수 확인")
    try:
        result = manager.client.table('articles').select('issue_id').execute()
        if result.data:
            issue_counts = {}
            for article in result.data:
                issue_id = article.get('issue_id')
                if issue_id:  # None이 아닌 경우만
                    issue_counts[issue_id] = issue_counts.get(issue_id, 0) + 1
            
            if issue_counts:
                print("📋 이슈별 기사 수:")
                for issue_id, count in sorted(issue_counts.items()):
                    print(f"   이슈 ID {issue_id}: {count:,}개")
            else:
                print("⚠️ 이슈가 할당된 기사가 없습니다")
        else:
            print("⚠️ 이슈별 기사가 없습니다")
    except Exception as e:
        print(f"❌ 이슈별 기사 수 조회 실패: {e}")
    
    # 5. 편향성별 기사 수 확인
    print("\n🔍 5. 편향성별 기사 수 확인")
    try:
        result = manager.client.table('articles').select('bias').execute()
        if result.data:
            bias_counts = {}
            for article in result.data:
                bias = article.get('bias')
                if bias is None:
                    bias = 'Unknown'
                bias_counts[bias] = bias_counts.get(bias, 0) + 1
            
            print("🎭 편향성별 기사 수:")
            for bias, count in sorted(bias_counts.items()):
                print(f"   {bias}: {count:,}개")
        else:
            print("⚠️ 편향성별 기사가 없습니다")
    except Exception as e:
        print(f"❌ 편향성별 기사 수 조회 실패: {e}")
    
    # 6. 날짜별 기사 수 확인 (최근 7일)
    print("\n🔍 6. 최근 7일간 기사 수 확인")
    try:
        from datetime import datetime, timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        
        result = manager.client.table('articles').select(
            'published_at'
        ).gte('published_at', start_date.isoformat()).lte('published_at', end_date.isoformat()).execute()
        
        if result.data:
            daily_counts = {}
            for article in result.data:
                published_at = article.get('published_at')
                if published_at:
                    try:
                        date_str = published_at[:10]  # YYYY-MM-DD 부분만 추출
                        daily_counts[date_str] = daily_counts.get(date_str, 0) + 1
                    except:
                        pass
            
            if daily_counts:
                print("📅 최근 7일간 일별 기사 수:")
                for date_str in sorted(daily_counts.keys()):
                    print(f"   {date_str}: {daily_counts[date_str]:,}개")
            else:
                print("⚠️ 최근 7일간 기사가 없습니다")
        else:
            print("⚠️ 최근 7일간 기사가 없습니다")
    except Exception as e:
        print(f"❌ 최근 7일간 기사 수 조회 실패: {e}")

    # 7. 데이터베이스 테이블 구조 분석
    print("\n🔍 7. 데이터베이스 테이블 구조 분석")
    try:
        # articles 테이블의 컬럼 정보 확인
        print("📋 articles 테이블 컬럼 정보:")
        sample_article = manager.client.table('articles').select('*').limit(1).execute()
        if sample_article.data:
            article_keys = list(sample_article.data[0].keys())
            print(f"   컬럼 목록: {', '.join(article_keys)}")
            
            # media_id 필드의 실제 값들 확인
            print("\n🔍 media_id 필드 값 분석:")
            media_id_values = manager.client.table('articles').select('media_id').execute()
            if media_id_values.data:
                unique_media_ids = set()
                null_count = 0
                for article in media_id_values.data:
                    media_id = article.get('media_id')
                    if media_id is None:
                        null_count += 1
                    else:
                        unique_media_ids.add(media_id)
                
                print(f"   고유한 media_id 값들: {sorted(unique_media_ids)}")
                print(f"   media_id가 null인 기사: {null_count:,}개")
                print(f"   media_id가 있는 기사: {len(media_id_values.data) - null_count:,}개")
                
                # media_outlets 테이블 확인
                print("\n🔍 media_outlets 테이블 확인:")
                try:
                    media_outlets = manager.client.table('media_outlets').select('*').execute()
                    if media_outlets.data:
                        print(f"   media_outlets 테이블 레코드 수: {len(media_outlets.data):,}개")
                        print("   미디어 아울렛 목록:")
                        for outlet in media_outlets.data:
                            print(f"     ID: {outlet.get('id')}, 이름: {outlet.get('name')}, 편향성: {outlet.get('bias')}")
                    else:
                        print("   ⚠️ media_outlets 테이블에 데이터가 없습니다")
                except Exception as e:
                    print(f"   ❌ media_outlets 테이블 조회 실패: {e}")
        else:
            print("⚠️ articles 테이블에서 샘플 데이터를 가져올 수 없습니다")
    except Exception as e:
        print(f"❌ 테이블 구조 분석 실패: {e}")

if __name__ == "__main__":
    check_articles_table()

