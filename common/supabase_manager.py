import os
from typing import List, Dict, Optional, Any
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
from datetime import datetime

# 환경 변수 로드
load_dotenv()

class SupabaseManager:
    """
    Supabase 데이터베이스 관리자
    - 뉴스 데이터 저장 및 조회
    - 테이블 생성 및 관리
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.client: Optional[Client] = None
        
        # Supabase 클라이언트 초기화
        self._init_client()
    
    def _init_client(self):
        """Supabase 클라이언트 초기화"""
        try:
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_KEY')
            
            if not supabase_url or not supabase_key:
                self.logger.error("Supabase 환경 변수가 설정되지 않았습니다.")
                self.logger.error("SUPABASE_URL과 SUPABASE_KEY를 환경 변수에 설정해주세요.")
                return
            
            self.client = create_client(supabase_url, supabase_key)
            self.logger.info("Supabase 클라이언트 초기화 성공")
            
        except Exception as e:
            self.logger.error(f"Supabase 클라이언트 초기화 실패: {str(e)}")
    
    def is_connected(self) -> bool:
        """Supabase 연결 상태 확인"""
        return self.client is not None
    
    def create_news_table_if_not_exists(self, table_name: str):
        """뉴스 테이블 생성"""
        if not self.is_connected():
            return False
        
        try:
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                title TEXT NOT NULL,
                deck TEXT,
                link TEXT NOT NULL UNIQUE,
                time TEXT,
                author TEXT,
                img_url TEXT,
                content TEXT,
                category TEXT,
                source TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_{table_name}_link ON {table_name}(link);
            CREATE INDEX IF NOT EXISTS idx_{table_name}_category ON {table_name}(category);
            CREATE INDEX IF NOT EXISTS idx_{table_name}_created_at ON {table_name}(created_at);
            """
            
            result = self.client.rpc('exec_sql', {'sql': create_table_sql}).execute()
            self.logger.info(f"뉴스 테이블 {table_name} 생성/확인 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"뉴스 테이블 생성 실패: {str(e)}")
            return False
    
    def insert_news(self, news_data: Dict, table_name: str) -> bool:
        """뉴스 기사 삽입"""
        if not self.is_connected():
            return False
        
        try:
            result = self.client.table(table_name).insert(news_data).execute()
            if result.data:
                self.logger.info(f"기사 저장 성공: {news_data.get('title', '제목 없음')}")
                return True
            else:
                self.logger.warning(f"기사 저장 실패: {news_data.get('title', '제목 없음')}")
                return False
                
        except Exception as e:
            self.logger.error(f"기사 저장 중 오류: {str(e)}")
            return False
    
    def get_news_by_link(self, link: str, table_name: str) -> Optional[Dict]:
        """링크로 기사 조회"""
        if not self.is_connected():
            return None
        
        try:
            result = self.client.table(table_name).select('*').eq('link', link).execute()
            if result.data:
                return result.data[0]
            return None
            
        except Exception as e:
            self.logger.error(f"기사 조회 중 오류: {str(e)}")
            return None
    
    def get_news_count(self, table_name: str) -> int:
        """테이블의 기사 개수 조회"""
        if not self.is_connected():
            return 0
        
        try:
            result = self.client.table(table_name).select('id', count='exact').execute()
            return result.count or 0
            
        except Exception as e:
            self.logger.error(f"기사 개수 조회 중 오류: {str(e)}")
            return 0
