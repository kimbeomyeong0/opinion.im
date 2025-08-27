#!/usr/bin/env python3
"""
기사 전처리 실행 스크립트
"""

import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.article_preprocessor import ArticlePreprocessor

def main():
    """전처리 실행"""
    print("🔍 OPINION.IM 기사 전처리 시작")
    print("=" * 50)
    
    try:
        # 전처리 실행
        preprocessor = ArticlePreprocessor()
        success = preprocessor.preprocess_articles()
        
        if success:
            print("\n✅ 전처리가 성공적으로 완료되었습니다!")
            print("📊 데이터 품질이 향상되었습니다.")
        else:
            print("\n❌ 전처리 중 오류가 발생했습니다.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⚠️ 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 예상치 못한 오류가 발생했습니다: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
