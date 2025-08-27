#!/usr/bin/env python3
"""
OpenAI 임베딩 생성 실행 스크립트
"""

import sys
import os
import argparse
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.embedding_generator import EmbeddingGenerator

def main():
    """임베딩 생성 실행"""
    # 명령행 인수 파싱
    parser = argparse.ArgumentParser(description='OpenAI 임베딩 생성 스크립트')
    parser.add_argument('--limit', type=int, help='테스트용 기사 개수 제한 (예: --limit 10)')
    args = parser.parse_args()
    
    print("🚀 OPINION.IM OpenAI 임베딩 생성 시작")
    print("=" * 60)
    
    # 테스트 실행 정보 표시
    if args.limit:
        print(f"📊 테스트 실행: {args.limit}개 기사만 임베딩")
        print("=" * 60)
    
    try:
        # 임베딩 생성 실행
        generator = EmbeddingGenerator(limit=args.limit)
        success = generator.embed_articles()
        
        if success:
            print("\n🎉 임베딩 생성이 성공적으로 완료되었습니다!")
            stats = generator.get_embedding_stats()
            print(f"📊 새로 생성된 임베딩: {stats['newly_embedded']}개")
            print(f"📊 이미 존재하는 임베딩: {stats['already_embedded']}개")
            print(f"📊 임베딩 실패: {stats['failed_embeddings']}개")
            
            # 소요 시간 표시
            if stats.get('start_time') and stats.get('end_time'):
                duration = stats['end_time'] - stats['start_time']
                print(f"⏱️ 총 소요 시간: {str(duration).split('.')[0]}")
            
            # 성공률 계산
            if stats['total_articles'] > 0:
                success_rate = (stats['newly_embedded'] / stats['total_articles']) * 100
                print(f"🎯 성공률: {success_rate:.1f}%")
        else:
            print("\n❌ 임베딩 생성 중 오류가 발생했습니다.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 예상치 못한 오류가 발생했습니다: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
