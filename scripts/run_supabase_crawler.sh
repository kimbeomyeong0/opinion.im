#!/bin/bash

echo "조선일보 정치 크롤러 (Supabase 연동) 실행 중..."
echo "================================================"

# 환경 변수 확인
if [ -z "$SUPABASE_URL" ] || [ -z "$SUPABASE_KEY" ]; then
    echo "⚠️  Supabase 환경 변수가 설정되지 않았습니다."
    echo "다음 환경 변수를 설정해주세요:"
    echo "export SUPABASE_URL=your_supabase_project_url"
    echo "export SUPABASE_KEY=your_supabase_anon_key"
    echo ""
    echo "로컬 JSON 저장만 사용합니다."
fi

# Python 가상환경이 있다면 활성화
if [ -d "venv" ]; then
    echo "가상환경 활성화 중..."
    source venv/bin/activate
fi

# 필요한 패키지 설치 확인
echo "필요한 패키지 설치 확인 중..."
pip install -r requirements.txt

# Supabase 연결 테스트
echo "Supabase 연결 테스트 중..."
python -c "
from supabase_manager import SupabaseManager
manager = SupabaseManager()
if manager.is_connected():
    print('✅ Supabase 연결 성공')
    manager.display_database_stats()
else:
    print('❌ Supabase 연결 실패')
"

# 크롤러 실행
echo "크롤러 실행 중..."
python chosun_politics_crawler.py

echo "================================================"
echo "크롤링 완료!"

