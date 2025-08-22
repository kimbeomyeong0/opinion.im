# 조선일보 정치 크롤러 설정 파일

# Supabase 설정
SUPABASE_CONFIG = {
    'url': 'your_supabase_project_url',  # 환경 변수에서 가져올 예정
    'key': 'your_supabase_anon_key',    # 환경 변수에서 가져올 예정
    'table_name': 'chosun_politics_news',  # 뉴스 저장 테이블명
    'batch_size': 50,  # 한 번에 저장할 데이터 수
}

# 크롤링 설정
CRAWLER_CONFIG = {
    'max_workers': 5,        # 동시 작업자 수 (노트북 과열 방지를 위해 낮게 설정)
    'timeout': 15,           # 요청 타임아웃 (초)
    'target_count': 100,     # 목표 기사 수
    'delay_between_requests': 1,  # 요청 간 지연 시간 (초)
}

# URL 설정
URLS = {
    'base': 'https://www.chosun.com',
    'politics': 'https://www.chosun.com/politics/',
    'north_korea': 'https://www.chosun.com/politics/north_korea/',
    'politics_general': 'https://www.chosun.com/politics/politics_general/'
}

# HTML 선택자 설정
SELECTORS = {
    'story_card': '.story-card-container',
    'title': '.story-card__headline span',
    'deck': '.story-card__deck span',
    'link': '.story-card__headline a',
    'time': '.story-card__sigline-datetime .text',
    'article_title': '.article-header__headline span',
    'article_time': '.upDate',
    'article_body': '.article-body',
    'article_text': 'p.article-body__content-text',
    'load_more': '.load-more-btn'
}

# User-Agent 설정
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
]

# 카테고리 매핑
CATEGORY_MAPPING = {
    '/north_korea/': '북한',
    '/politics_general/': '정치일반',
    '/politics/': '정치'
}

# 출력 설정
OUTPUT_CONFIG = {
    'filename_prefix': 'chosun_politics',
    'encoding': 'utf-8',
    'indent': 2,
    'ensure_ascii': False
}

# 로깅 설정
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
}

# 데이터베이스 스키마 설정
DB_SCHEMA = {
    'table_name': 'chosun_politics_news',
    'columns': {
        'id': 'uuid DEFAULT gen_random_uuid() PRIMARY KEY',
        'title': 'text NOT NULL',
        'deck': 'text',
        'link': 'text NOT NULL UNIQUE',
        'time': 'text',
        'author': 'text',
        'img_url': 'text',
        'content': 'text',
        'category': 'text',
        'source': 'text DEFAULT \'조선일보\'',
        'created_at': 'timestamp with time zone DEFAULT now()',
        'updated_at': 'timestamp with time zone DEFAULT now()'
    }
}
