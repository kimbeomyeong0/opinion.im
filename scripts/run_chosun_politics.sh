#!/bin/bash

echo "조선일보 정치 크롤러 실행 중..."
echo "================================"

# Python 가상환경이 있다면 활성화
if [ -d "venv" ]; then
    echo "가상환경 활성화 중..."
    source venv/bin/activate
fi

# 필요한 패키지 설치 확인
echo "필요한 패키지 설치 확인 중..."
pip install -r requirements.txt

# 크롤러 실행
echo "크롤러 실행 중..."
python chosun_politics_crawler.py

echo "================================"
echo "크롤링 완료!"
