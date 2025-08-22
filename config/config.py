# 크롤러 설정 파일
CRAWLER_CONFIG = {
    'max_workers': 8,           # 최대 워커 수
    'timeout': 10,              # 타임아웃 (초)
    'max_retries': 3,           # 최대 재시도 횟수
    'delay_between_requests': 0.1,  # 요청 간 지연시간 (초)
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# 언론사 URL 목록
NEWS_SOURCES = {
    '종합지': [
        'https://www.yna.co.kr/',
        'https://www.hani.co.kr/',
        'https://www.khan.co.kr/',
        'https://www.donga.com/',
        'https://www.chosun.com/',
        'https://www.joongang.co.kr/',
        'https://www.seoul.co.kr/',
        'https://www.kmib.co.kr/',
        'https://www.munhwa.com/',
        'https://www.kyunghyang.com/'
    ],
    '경제지': [
        'https://www.mk.co.kr/',
        'https://www.hankyung.com/',
        'https://www.edaily.co.kr/',
        'https://www.fnnews.com/',
        'https://www.etnews.com/'
    ],
    '스포츠지': [
        'https://sports.news.naver.com/',
        'https://sports.donga.com/',
        'https://sports.chosun.com/',
        'https://sports.khan.co.kr/'
    ]
}

