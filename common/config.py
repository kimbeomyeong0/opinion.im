#!/usr/bin/env python3
"""
공통 설정 관리
환경변수 로드 및 상수값 관리
"""

import os
from dotenv import load_dotenv
from typing import Dict, List, Any

# 환경 변수 로드
load_dotenv()

class Config:
    """설정 관리 클래스"""
    
    # Supabase 설정
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    
    # 크롤러 기본 설정
    MAX_WORKERS = int(os.getenv('MAX_WORKERS', '8'))
    TIMEOUT = int(os.getenv('TIMEOUT', '10'))
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    DELAY_BETWEEN_REQUESTS = float(os.getenv('DELAY_BETWEEN_REQUESTS', '0.1'))
    
    # User Agent
    USER_AGENT = os.getenv('USER_AGENT', 
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    )
    
    # 로깅 설정
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    
    # 데이터베이스 테이블명 패턴
    TABLE_NAME_PATTERN = "{source}_politics_news"
    
    # 언론사별 설정
    NEWS_SOURCES = {
        'major_news': {
            'chosun': {
                'name': '조선일보',
                'base_url': 'https://www.chosun.com',
                'politics_url': 'https://www.chosun.com/politics/',
                'table_name': 'chosun_politics_news'
            },
            'donga': {
                'name': '동아일보',
                'base_url': 'https://www.donga.com',
                'politics_url': 'https://www.donga.com/news/Politics',
                'table_name': 'donga_politics_news'
            },
            'hani': {
                'name': '한겨레',
                'base_url': 'https://www.hani.co.kr',
                'politics_url': 'https://www.hani.co.kr/arti/politics/',
                'table_name': 'hani_politics_news'
            },
            'hankyung': {
                'name': '한국경제',
                'base_url': 'https://www.hankyung.com',
                'politics_url': 'https://www.hankyung.com/politics',
                'table_name': 'hankyung_politics_news'
            },
            'joongang': {
                'name': '중앙일보',
                'base_url': 'https://www.joongang.co.kr',
                'politics_url': 'https://www.joongang.co.kr/politics',
                'table_name': 'joongang_politics_news'
            },
            'jtbc': {
                'name': 'JTBC',
                'base_url': 'https://news.jtbc.co.kr',
                'politics_url': 'https://news.jtbc.co.kr/politics',
                'table_name': 'jtbc_politics_news'
            },
            'kbs': {
                'name': 'KBS',
                'base_url': 'https://news.kbs.co.kr',
                'politics_url': 'https://news.kbs.co.kr/news/politics',
                'table_name': 'kbs_politics_news'
            },
            'khan': {
                'name': '경향신문',
                'base_url': 'https://www.khan.co.kr',
                'politics_url': 'https://www.khan.co.kr/politics',
                'table_name': 'khan_politics_news'
            },
            'kmib': {
                'name': '국민일보',
                'base_url': 'https://www.kmib.co.kr',
                'politics_url': 'https://www.kmib.co.kr/news/politics',
                'table_name': 'kmib_politics_news'
            },
            'mk': {
                'name': '매일경제',
                'base_url': 'https://www.mk.co.kr',
                'politics_url': 'https://www.mk.co.kr/news/politics',
                'table_name': 'mk_politics_news'
            },
            'munhwa': {
                'name': '문화일보',
                'base_url': 'https://www.munhwa.com',
                'politics_url': 'https://www.munhwa.com/news/politics',
                'table_name': 'munhwa_politics_news'
            },
            'news1': {
                'name': '뉴스1',
                'base_url': 'https://www.news1.kr',
                'politics_url': 'https://www.news1.kr/politics',
                'table_name': 'news1_politics_news'
            },
            'sbs': {
                'name': 'SBS',
                'base_url': 'https://news.sbs.co.kr',
                'politics_url': 'https://news.sbs.co.kr/news/politics',
                'table_name': 'sbs_politics_news'
            },
            'sedaily': {
                'name': '서울경제',
                'base_url': 'https://www.sedaily.com',
                'politics_url': 'https://www.sedaily.com/NewsList/GP01',
                'table_name': 'sedaily_politics_news'
            },
            'segye': {
                'name': '세계일보',
                'base_url': 'https://www.segye.com',
                'politics_url': 'https://www.segye.com/news/politics',
                'table_name': 'segye_politics_news'
            },
            'yna': {
                'name': '연합뉴스',
                'base_url': 'https://www.yna.co.kr',
                'politics_url': 'https://www.yna.co.kr/politics',
                'table_name': 'yna_politics_news'
            },
            'ytn': {
                'name': 'YTN',
                'base_url': 'https://www.ytn.co.kr',
                'politics_url': 'https://www.ytn.co.kr/news/politics',
                'table_name': 'ytn_politics_news'
            }
        },
        'online_news': {
            'ohmynews': {
                'name': '오마이뉴스',
                'base_url': 'https://www.ohmynews.com',
                'politics_url': 'https://www.ohmynews.com/NWS_Web/ArticleView/at_pg.aspx?CNTN_CD=A0000000000',
                'table_name': 'ohmynews_politics_news'
            },
            'pressian': {
                'name': '프레시안',
                'base_url': 'https://www.pressian.com',
                'politics_url': 'https://www.pressian.com/pages/politics',
                'table_name': 'pressian_politics_news'
            }
        },
        'broadcasting': {
            'mbc': {
                'name': 'MBC',
                'base_url': 'https://imnews.imbc.com',
                'politics_url': 'https://imnews.imbc.com/news/politics',
                'table_name': 'mbc_politics_news'
            }
        }
    }
    
    @classmethod
    def get_source_config(cls, source_type: str, source_name: str) -> Dict[str, Any]:
        """언론사별 설정 반환"""
        return cls.NEWS_SOURCES.get(source_type, {}).get(source_name, {})
    
    @classmethod
    def get_all_sources(cls) -> List[str]:
        """모든 언론사 이름 반환"""
        sources = []
        for source_type in cls.NEWS_SOURCES.values():
            sources.extend(source_type.keys())
        return sources
    
    @classmethod
    def get_sources_by_type(cls, source_type: str) -> List[str]:
        """특정 타입의 언론사 이름 반환"""
        return list(cls.NEWS_SOURCES.get(source_type, {}).keys())
    
    @classmethod
    def validate_config(cls) -> bool:
        """설정 유효성 검사"""
        if not cls.SUPABASE_URL:
            print("경고: SUPABASE_URL이 설정되지 않았습니다.")
            return False
        
        if not cls.SUPABASE_KEY:
            print("경고: SUPABASE_KEY가 설정되지 않았습니다.")
            return False
        
        return True

# 전역 설정 인스턴스
config = Config()
