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

class SupabaseManagerV2:
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
    
    # ===== Issues 관련 메서드 =====
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
    
    def update_issue_bias(self, issue_id: int, bias_data: Dict[str, float]) -> bool:
        """이슈 편향성 업데이트"""
        if not self.is_connected():
            return False
        
        try:
            # 편향성 퍼센트 계산
            total = sum(bias_data.values())
            if total > 0:
                bias_left_pct = (bias_data.get('left', 0) / total) * 100
                bias_center_pct = (bias_data.get('center', 0) / total) * 100
                bias_right_pct = (bias_data.get('right', 0) / total) * 100
                
                # 주요 편향성 결정
                dominant_bias = max(bias_data.items(), key=lambda x: x[1])[0].upper()
                
                update_data = {
                    'bias_left_pct': round(bias_left_pct, 2),
                    'bias_center_pct': round(bias_center_pct, 2),
                    'bias_right_pct': round(bias_right_pct, 2),
                    'dominant_bias': dominant_bias
                }
                
                self.client.table('issues').update(update_data).eq('id', issue_id).execute()
                self.logger.info(f"이슈 편향성 업데이트 성공: {issue_id}")
                return True
                
        except Exception as e:
            self.logger.error(f"이슈 편향성 업데이트 실패: {str(e)}")
            return False
    
    # ===== Media Outlets 관련 메서드 =====
    def get_media_outlet(self, name: str) -> Optional[Dict]:
        """언론사 정보 조회"""
        if not self.is_connected():
            return None
        
        try:
            result = self.client.table('media_outlets').select('*').eq('name', name).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            self.logger.error(f"언론사 조회 실패: {str(e)}")
            return None
    
    def create_media_outlet(self, name: str, bias: str) -> Optional[int]:
        """새로운 언론사 생성"""
        if not self.is_connected():
            return None
        
        try:
            data = {'name': name, 'bias': bias}
            result = self.client.table('media_outlets').insert(data).execute()
            if result.data:
                outlet_id = result.data[0]['id']
                self.logger.info(f"언론사 생성 성공: {name} (ID: {outlet_id})")
                return outlet_id
            return None
            
        except Exception as e:
            self.logger.error(f"언론사 생성 실패: {str(e)}")
            return None
    
    # ===== Articles 관련 메서드 =====
    def insert_article(self, article_data: Dict[str, Any]) -> Optional[int]:
        """기사 삽입"""
        if not self.is_connected():
            return None
        
        try:
            # 필수 필드 검증
            required_fields = ['issue_id', 'media_id', 'title', 'url']
            for field in required_fields:
                if not article_data.get(field):
                    self.logger.warning(f"필수 필드 누락: {field}")
                    return None
            
            # datetime 객체를 ISO 형식 문자열로 변환
            processed_data = article_data.copy()
            if 'published_at' in processed_data and processed_data['published_at']:
                if isinstance(processed_data['published_at'], datetime):
                    processed_data['published_at'] = processed_data['published_at'].isoformat()
            
            # 중복 체크 (URL 기준)
            existing = self.client.table('articles').select('id').eq('url', processed_data['url']).execute()
            
            if existing.data:
                # 기존 기사 업데이트
                result = self.client.table('articles').update(processed_data).eq('url', processed_data['url']).execute()
                article_id = result.data[0]['id']
                self.logger.info(f"기존 기사 업데이트: {processed_data['title']}")
            else:
                # 새 기사 삽입
                result = self.client.table('articles').insert(processed_data).execute()
                article_id = result.data[0]['id']
                self.logger.info(f"새 기사 삽입: {processed_data['title']}")
            
            return article_id
            
        except Exception as e:
            self.logger.error(f"기사 삽입 실패: {str(e)}")
            return None
    
    def insert_articles_batch(self, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """여러 기사를 배치로 삽입"""
        if not self.is_connected():
            return {'success': False, 'message': 'Supabase에 연결되지 않음'}
        
        results = {
            'total': len(articles),
            'success': 0,
            'failed': 0,
            'errors': []
        }
        
        try:
            for article in articles:
                if self.insert_article(article):
                    results['success'] += 1
                else:
                    results['failed'] += 1
                    results['errors'].append(f"실패: {article.get('title', '제목 없음')}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"배치 삽입 실패: {str(e)}")
            results['errors'].append(f"배치 처리 에러: {str(e)}")
            return results
    
    # ===== Bias Summaries 관련 메서드 =====
    def insert_bias_summary(self, issue_id: int, bias: str, summary: str) -> bool:
        """편향성별 요약 삽입"""
        if not self.is_connected():
            return False
        
        try:
            data = {
                'issue_id': issue_id,
                'bias': bias,
                'summary': summary
            }
            
            # 기존 요약이 있으면 업데이트, 없으면 삽입
            existing = self.client.table('bias_summaries').select('id').eq('issue_id', issue_id).eq('bias', bias).execute()
            
            if existing.data:
                self.client.table('bias_summaries').update(data).eq('id', existing.data[0]['id']).execute()
                self.logger.info(f"편향성 요약 업데이트: {bias}")
            else:
                self.client.table('bias_summaries').insert(data).execute()
                self.logger.info(f"편향성 요약 삽입: {bias}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"편향성 요약 삽입 실패: {str(e)}")
            return False
    
    # ===== Media Summaries 관련 메서드 =====
    def insert_media_summary(self, issue_id: int, media_id: int, summary: str) -> bool:
        """언론사별 요약 삽입"""
        if not self.is_connected():
            return False
        
        try:
            data = {
                'issue_id': issue_id,
                'media_id': media_id,
                'summary': summary
            }
            
            # 기존 요약이 있으면 업데이트, 없으면 삽입
            existing = self.client.table('media_summaries').select('id').eq('issue_id', issue_id).eq('media_id', media_id).execute()
            
            if existing.data:
                self.client.table('media_summaries').update(data).eq('id', existing.data[0]['id']).execute()
                self.logger.info(f"언론사 요약 업데이트: {media_id}")
            else:
                self.client.table('media_summaries').insert(data).execute()
                self.logger.info(f"언론사 요약 삽입: {media_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"언론사 요약 삽입 실패: {str(e)}")
            return False
    
    # ===== Common Points 관련 메서드 =====
    def insert_common_points(self, issue_id: int, points: List[str]) -> bool:
        """공통점 삽입"""
        if not self.is_connected():
            return False
        
        try:
            # 기존 공통점 삭제
            self.client.table('common_points').delete().eq('issue_id', issue_id).execute()
            
            # 새 공통점 삽입
            for point in points:
                data = {'issue_id': issue_id, 'point': point}
                self.client.table('common_points').insert(data).execute()
            
            self.logger.info(f"공통점 {len(points)}개 삽입 완료")
            return True
            
        except Exception as e:
            self.logger.error(f"공통점 삽입 실패: {str(e)}")
            return False
    
    # ===== 통계 및 조회 메서드 =====
    def get_articles_by_issue(self, issue_id: int) -> List[Dict]:
        """이슈별 기사 조회"""
        if not self.is_connected():
            return []
        
        try:
            result = self.client.table('articles').select('*').eq('issue_id', issue_id).execute()
            return result.data or []
        except Exception as e:
            self.logger.error(f"이슈별 기사 조회 실패: {str(e)}")
            return []
    
    def get_articles_by_media(self, media_id: int, limit: int = 50) -> List[Dict]:
        """언론사별 기사 조회"""
        if not self.is_connected():
            return []
        
        try:
            result = self.client.table('articles').select('*').eq('media_id', media_id).order('published_at', desc=True).limit(limit).execute()
            return result.data or []
        except Exception as e:
            self.logger.error(f"언론사별 기사 조회 실패: {str(e)}")
            return []
    
    def display_database_stats(self):
        """데이터베이스 통계 표시"""
        if not self.is_connected():
            self.console.print("[red]데이터베이스에 연결되지 않았습니다.[/red]")
            return
        
        try:
            # 이슈 수
            issues_result = self.client.table('issues').select('id', count='exact').execute()
            issues_count = issues_result.count or 0
            
            # 기사 수
            articles_result = self.client.table('articles').select('id', count='exact').execute()
            articles_count = articles_result.count or 0
            
            # 언론사 수
            outlets_result = self.client.table('media_outlets').select('id', count='exact').execute()
            outlets_count = outlets_result.count or 0
            
            # 통계 테이블 표시
            table = Table(title="OPINION.IM 데이터베이스 통계")
            table.add_column("항목", style="cyan")
            table.add_column("수치", style="magenta")
            
            table.add_row("총 이슈 수", str(issues_count))
            table.add_row("총 기사 수", str(articles_count))
            table.add_row("등록된 언론사 수", str(outlets_count))
            
            self.console.print(table)
            
        except Exception as e:
            self.logger.error(f"통계 표시 실패: {str(e)}")
            self.console.print(f"[red]통계 표시 실패: {str(e)}[/red]")

if __name__ == "__main__":
    # 테스트
    manager = SupabaseManagerV2()
    if manager.is_connected():
        manager.display_database_stats()
    else:
        print("Supabase 연결 실패")
