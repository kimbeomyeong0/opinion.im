import os
from typing import List, Dict, Optional
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import json
from datetime import datetime

# 환경 변수 로드
load_dotenv()

class SupabaseManager:
    def __init__(self):
        self.console = Console()
        self.client: Optional[Client] = None
        self.table_name = 'chosun_politics_news'
        
        # 로깅 설정
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Supabase 클라이언트 초기화
        self._init_client()
    
    def _init_client(self):
        """Supabase 클라이언트 초기화"""
        try:
            supabase_url = os.getenv('SUPABASE_URL')
            supabase_key = os.getenv('SUPABASE_KEY')
            
            if not supabase_url or not supabase_key:
                self.console.print("[red]Supabase 환경 변수가 설정되지 않았습니다.[/red]")
                self.console.print("[yellow]SUPABASE_URL과 SUPABASE_KEY를 환경 변수에 설정해주세요.[/yellow]")
                return
            
            self.client = create_client(supabase_url, supabase_key)
            self.console.print("[green]Supabase 클라이언트 초기화 성공[/green]")
            
        except Exception as e:
            self.console.print(f"[red]Supabase 클라이언트 초기화 실패: {str(e)}[/red]")
            self.logger.error(f"Supabase 클라이언트 초기화 실패: {str(e)}")
    
    def is_connected(self) -> bool:
        """Supabase 연결 상태 확인"""
        return self.client is not None
    
    def create_table_if_not_exists(self):
        """테이블이 존재하지 않으면 생성"""
        if not self.is_connected():
            self.console.print("[red]Supabase에 연결되지 않았습니다.[/red]")
            return False
        
        try:
            # 테이블 생성 SQL (PostgreSQL)
            create_table_sql = f"""
            CREATE TABLE IF NOT EXISTS {self.table_name} (
                id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
                title TEXT NOT NULL,
                deck TEXT,
                link TEXT NOT NULL UNIQUE,
                time TEXT,
                author TEXT,
                img_url TEXT,
                content TEXT,
                category TEXT,
                source TEXT DEFAULT '조선일보',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            -- 인덱스 생성
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_link ON {self.table_name}(link);
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_category ON {self.table_name}(category);
            CREATE INDEX IF NOT EXISTS idx_{self.table_name}_created_at ON {self.table_name}(created_at);
            
            -- 업데이트 트리거 함수
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ language 'plpgsql';
            
            -- 업데이트 트리거
            DROP TRIGGER IF EXISTS update_{self.table_name}_updated_at ON {self.table_name};
            CREATE TRIGGER update_{self.table_name}_updated_at
                BEFORE UPDATE ON {self.table_name}
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column();
            """
            
            # SQL 실행 (rpc를 통해 실행)
            result = self.client.rpc('exec_sql', {'sql': create_table_sql}).execute()
            
            self.console.print(f"[green]테이블 {self.table_name} 생성/확인 완료[/green]")
            return True
            
        except Exception as e:
            self.console.print(f"[red]테이블 생성 실패: {str(e)}[/red]")
            self.logger.error(f"테이블 생성 실패: {str(e)}")
            return False
    
    def insert_news(self, news_data: Dict) -> bool:
        """단일 뉴스 데이터 삽입"""
        if not self.is_connected():
            return False
        
        try:
            # 데이터 정리
            clean_data = {
                'title': news_data.get('title', ''),
                'deck': news_data.get('deck', ''),
                'link': news_data.get('link', ''),
                'time': news_data.get('time', ''),
                'author': news_data.get('author', ''),
                'img_url': news_data.get('img_url', ''),
                'content': news_data.get('content', ''),
                'category': news_data.get('category', ''),
                'source': news_data.get('source', '조선일보')
            }
            
            # 필수 필드 검증
            if not clean_data['title'] or not clean_data['link']:
                self.logger.warning(f"필수 필드 누락: {clean_data}")
                return False
            
            # 중복 체크 (link 기준)
            existing = self.client.table(self.table_name).select('id').eq('link', clean_data['link']).execute()
            
            if existing.data:
                # 기존 데이터 업데이트
                result = self.client.table(self.table_name).update(clean_data).eq('link', clean_data['link']).execute()
                self.logger.info(f"기존 기사 업데이트: {clean_data['title']}")
            else:
                # 새 데이터 삽입
                result = self.client.table(self.table_name).insert(clean_data).execute()
                self.logger.info(f"새 기사 삽입: {clean_data['title']}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"뉴스 삽입 실패: {str(e)}")
            return False
    
    def insert_news_batch(self, news_list: List[Dict]) -> Dict:
        """여러 뉴스 데이터를 배치로 삽입"""
        if not self.is_connected():
            return {'success': False, 'message': 'Supabase에 연결되지 않음'}
        
        results = {
            'total': len(news_list),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        try:
            # 배치 크기로 나누어 처리
            batch_size = 50
            for i in range(0, len(news_list), batch_size):
                batch = news_list[i:i + batch_size]
                
                for news in batch:
                    if self.insert_news(news):
                        results['success'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append(f"실패: {news.get('title', '제목 없음')}")
                
                self.console.print(f"[green]배치 처리 중... {min(i + batch_size, len(news_list))}/{len(news_list)}[/green]")
            
            return results
            
        except Exception as e:
            self.logger.error(f"배치 삽입 실패: {str(e)}")
            results['errors'].append(f"배치 처리 에러: {str(e)}")
            return results
    
    def get_news_count(self) -> int:
        """저장된 뉴스 개수 조회"""
        if not self.is_connected():
            return 0
        
        try:
            result = self.client.table(self.table_name).select('id', count='exact').execute()
            return result.count or 0
        except Exception as e:
            self.logger.error(f"뉴스 개수 조회 실패: {str(e)}")
            return 0
    
    def get_recent_news(self, limit: int = 10) -> List[Dict]:
        """최근 뉴스 조회"""
        if not self.is_connected():
            return []
        
        try:
            result = self.client.table(self.table_name).select('*').order('created_at', desc=True).limit(limit).execute()
            return result.data or []
        except Exception as e:
            self.logger.error(f"최근 뉴스 조회 실패: {str(e)}")
            return []
    
    def get_news_by_category(self, category: str, limit: int = 20) -> List[Dict]:
        """카테고리별 뉴스 조회"""
        if not self.is_connected():
            return []
        
        try:
            result = self.client.table(self.table_name).select('*').eq('category', category).order('created_at', desc=True).limit(limit).execute()
            return result.data or []
        except Exception as e:
            self.logger.error(f"카테고리별 뉴스 조회 실패: {str(e)}")
            return []
    
    def display_database_stats(self):
        """데이터베이스 통계 표시"""
        if not self.is_connected():
            self.console.print("[red]데이터베이스에 연결되지 않았습니다.[/red]")
            return
        
        try:
            # 전체 뉴스 수
            total_count = self.get_news_count()
            
            # 카테고리별 통계
            categories = ['정치', '북한', '정치일반']
            category_stats = {}
            
            for category in categories:
                count = len(self.get_news_by_category(category, limit=1000))
                category_stats[category] = count
            
            # 최근 뉴스
            recent_news = self.get_recent_news(5)
            
            # 통계 테이블 표시
            table = Table(title="데이터베이스 통계")
            table.add_column("항목", style="cyan")
            table.add_column("수치", style="magenta")
            
            table.add_row("전체 뉴스 수", str(total_count))
            for category, count in category_stats.items():
                table.add_row(f"{category} 기사", str(count))
            
            self.console.print(table)
            
            # 최근 뉴스 표시
            if recent_news:
                self.console.print("\n[bold blue]최근 저장된 기사 (상위 5개)[/bold blue]")
                for i, news in enumerate(recent_news, 1):
                    self.console.print(f"[bold]{i}.[/bold] {news.get('title', '제목 없음')}")
                    self.console.print(f"   카테고리: {news.get('category', '카테고리 없음')}")
                    self.console.print(f"   저장 시간: {news.get('created_at', '시간 정보 없음')}")
                    self.console.print()
            
        except Exception as e:
            self.logger.error(f"통계 표시 실패: {str(e)}")
            self.console.print(f"[red]통계 표시 실패: {str(e)}[/red]")
    
    def export_to_json(self, filename: str = None) -> str:
        """데이터베이스의 모든 뉴스를 JSON으로 내보내기"""
        if not self.is_connected():
            return ""
        
        try:
            # 모든 뉴스 조회
            result = self.client.table(self.table_name).select('*').order('created_at', desc=True).execute()
            news_data = result.data or []
            
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"supabase_export_{timestamp}.json"
            
            # JSON 파일로 저장
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(news_data, f, ensure_ascii=False, indent=2, default=str)
            
            self.console.print(f"[green]데이터가 {filename}에 내보내졌습니다. (총 {len(news_data)}개 기사)[/green]")
            return filename
            
        except Exception as e:
            self.logger.error(f"JSON 내보내기 실패: {str(e)}")
            self.console.print(f"[red]JSON 내보내기 실패: {str(e)}[/red]")
            return ""

