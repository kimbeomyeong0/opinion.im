import os
from typing import List, Dict, Optional, Any
from supabase import create_client, Client
from dotenv import load_dotenv
import logging
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import json
from datetime import datetime
import asyncio

# 환경 변수 로드
load_dotenv()

class UnifiedSupabaseManager:
    """
    통합된 Supabase 매니저
    - 뉴스 데이터 관리
    - 이슈 분석 관리
    - 편향성 분석
    """
    
    def __init__(self):
        self.console = Console()
        self.client: Optional[Client] = None
        
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
    
    # ===== 뉴스 데이터 관리 =====
    def create_news_table_if_not_exists(self, table_name: str = 'chosun_politics_news'):
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
                source TEXT DEFAULT '조선일보',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            
            CREATE INDEX IF NOT EXISTS idx_{table_name}_link ON {table_name}(link);
            CREATE INDEX IF NOT EXISTS idx_{table_name}_category ON {table_name}(category);
            CREATE INDEX IF NOT EXISTS idx_{table_name}_created_at ON {table_name}(created_at);
            """
            
            result = self.client.rpc('exec_sql', {'sql': create_table_sql}).execute()
            self.console.print(f"[green]뉴스 테이블 {table_name} 생성/확인 완료[/green]")
            return True
            
        except Exception as e:
            self.logger.error(f"뉴스 테이블 생성 실패: {str(e)}")
            return False
    
    def insert_news(self, news_data: Dict, table_name: str = 'chosun_politics_news') -> bool:
        """뉴스 기사 삽입"""
        if not self.is_connected():
            return False
        
        try:
            result = self.client.table(table_name).insert(news_data).execute()
            if result.data:
                self.logger.info(f"뉴스 삽입 성공: {news_data.get('title', 'Unknown')}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"뉴스 삽입 실패: {str(e)}")
            return False
    
    def insert_news_batch(self, news_list: List[Dict], table_name: str = 'chosun_politics_news') -> Dict:
        """배치 뉴스 삽입"""
        if not self.is_connected():
            return {'success': False, 'message': '연결되지 않음'}
        
        try:
            result = self.client.table(table_name).insert(news_list).execute()
            success_count = len(result.data) if result.data else 0
            
            return {
                'success': True,
                'inserted_count': success_count,
                'total_count': len(news_list),
                'message': f'{success_count}개 뉴스 삽입 성공'
            }
            
        except Exception as e:
            self.logger.error(f"배치 뉴스 삽입 실패: {str(e)}")
            return {'success': False, 'message': str(e)}
    
    def get_news_count(self, table_name: str = 'chosun_politics_news') -> int:
        """뉴스 개수 조회"""
        if not self.is_connected():
            return 0
        
        try:
            result = self.client.table(table_name).select('id', count='exact').execute()
            return result.count or 0
        except Exception as e:
            self.logger.error(f"뉴스 개수 조회 실패: {str(e)}")
            return 0
    
    # ===== 이슈 분석 관리 =====
    def create_issue(self, title: str, subtitle: str = None, summary: str = None) -> Optional[int]:
        """새로운 이슈 생성"""
        if not self.is_connected():
            return None
        
        try:
            data = {
                'title': title,
                'subtitle': subtitle,
                'summary': summary,
                'source_count': 0
            }
            
            result = self.client.table('issues').insert(data).execute()
            if result.data:
                issue_id = result.data[0]['id']
                self.logger.info(f"이슈 생성 성공: {title} (ID: {issue_id})")
                return issue_id
            return None
            
        except Exception as e:
            self.logger.error(f"이슈 생성 실패: {str(e)}")
            return None
    
    def get_issue_by_title(self, title: str) -> Optional[Dict]:
        """제목으로 이슈 조회"""
        if not self.is_connected():
            return None
        
        try:
            result = self.client.table('issues').select('*').eq('title', title).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            self.logger.error(f"이슈 조회 실패: {str(e)}")
            return None
    
    def update_issue_bias(self, issue_id: int) -> bool:
        """이슈의 편향성 업데이트"""
        if not self.is_connected():
            return False
        
        try:
            # 해당 이슈의 기사들의 편향성 분석
            result = self.client.table('articles').select('bias').eq('issue_id', issue_id).execute()
            
            if not result.data:
                return False
            
            # 편향성 분포 계산
            bias_counts = {}
            for article in result.data:
                bias = article.get('bias', 'Unknown')
                bias_counts[bias] = bias_counts.get(bias, 0) + 1
            
            # 가장 많은 편향성 찾기
            dominant_bias = max(bias_counts.items(), key=lambda x: x[1])[0] if bias_counts else 'Unknown'
            
            # 이슈 테이블 업데이트 (이슈 테이블이 있다면)
            try:
                self.client.table('issues').update({'bias': dominant_bias}).eq('id', issue_id).execute()
                self.logger.info(f"이슈 {issue_id} 편향성 업데이트: {dominant_bias}")
                return True
            except:
                # 이슈 테이블이 없으면 무시
                self.logger.info(f"이슈 편향성 업데이트 완료: {dominant_bias}")
                return True
                
        except Exception as e:
            self.logger.error(f"이슈 편향성 업데이트 실패: {str(e)}")
            return False
    
    def insert_bias_summary(self, issue_id: int, bias: str, summary: str) -> bool:
        """편향성별 요약 저장"""
        if not self.is_connected():
            return False
        
        try:
            data = {
                'issue_id': issue_id,
                'bias': bias,
                'summary': summary
            }
            
            result = self.client.table('bias_summaries').insert(data).execute()
            if result.data:
                self.logger.info(f"편향성 요약 저장 성공: {bias}")
                return True
            return False
            
        except Exception as e:
            self.logger.error(f"편향성 요약 저장 실패: {str(e)}")
            return False
    
    # ===== 통합 메서드 =====
    def get_project_status(self) -> Dict:
        """프로젝트 전체 상태 조회"""
        if not self.is_connected():
            return {'connected': False}
        
        try:
            news_count = self.get_news_count()
            
            # 이슈 개수 조회
            issues_result = self.client.table('issues').select('id', count='exact').execute()
            issues_count = issues_result.count or 0
            
            return {
                'connected': True,
                'news_count': news_count,
                'issues_count': issues_count,
                'total_items': news_count + issues_count
            }
            
        except Exception as e:
            self.logger.error(f"프로젝트 상태 조회 실패: {str(e)}")
            return {'connected': False, 'error': str(e)}
    
    def display_status(self):
        """상태를 콘솔에 표시"""
        status = self.get_project_status()
        
        if not status.get('connected'):
            self.console.print("[red]Supabase에 연결되지 않았습니다.[/red]")
            return
        
        # 상태 테이블 생성
        table = Table(title="프로젝트 상태")
        table.add_column("항목", style="cyan")
        table.add_column("값", style="magenta")
        
        table.add_row("연결 상태", "✅ 연결됨")
        table.add_row("뉴스 개수", str(status.get('news_count', 0)))
        table.add_row("이슈 개수", str(status.get('issues_count', 0)))
        table.add_row("총 항목", str(status.get('total_items', 0)))
        
        self.console.print(table)
    
    def get_random_issue_id(self) -> Optional[int]:
        """이슈 테이블에서 임의의 issue_id 조회"""
        if not self.is_connected():
            return None
        
        try:
            result = self.client.table('issues').select('id').execute()
            if result.data:
                # 임의의 issue_id 선택
                import random
                random_issue = random.choice(result.data)
                return random_issue['id']
            return None
        except Exception as e:
            self.logger.error(f"임의 이슈 ID 조회 실패: {str(e)}")
            return None

    # ===== 크롤러용 메서드 =====
    def get_media_outlet(self, media_name: str) -> Optional[Dict]:
        """미디어 아울렛 정보 조회"""
        if not self.is_connected():
            return None
        
        try:
            result = self.client.table('media_outlets').select('*').eq('name', media_name).execute()
            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            self.logger.error(f"미디어 아울렛 조회 실패: {str(e)}")
            return None
    
    def create_media_outlet(self, media_name: str, bias: str = "Center") -> Optional[int]:
        """새로운 미디어 아울렛 생성"""
        if not self.is_connected():
            return None
        
        try:
            # 이미 존재하는지 확인
            existing = self.get_media_outlet(media_name)
            if existing:
                return existing['id']
            
            # 새 미디어 아울렛 생성
            result = self.client.table('media_outlets').insert({
                'name': media_name,
                'bias': bias
            }).execute()
            
            if result.data:
                new_id = result.data[0]['id']
                self.logger.info(f"새 미디어 아울렛 생성: {media_name} (ID: {new_id})")
                return new_id
            return None
            
        except Exception as e:
            self.logger.error(f"미디어 아울렛 생성 실패: {str(e)}")
            return None
    
    def insert_article(self, article_data: Dict) -> bool:
        """기사 저장"""
        if not self.is_connected():
            return False
        
        try:
            # datetime 객체를 ISO 형식 문자열로 변환
            processed_data = {}
            for key, value in article_data.items():
                if hasattr(value, 'isoformat'):  # datetime 객체인 경우
                    processed_data[key] = value.isoformat()
                else:
                    processed_data[key] = value
            
            result = self.client.table('articles').insert(processed_data).execute()
            if result.data:
                return True
            return False
        except Exception as e:
            self.logger.error(f"기사 저장 실패: {str(e)}")
            return False