#!/usr/bin/env python3
"""
기사 전처리 모듈
- 중복 제거 (URL + media_id, content 유사도)
- 데이터 품질 관리
- 날짜 형식 통일
"""

import logging
from typing import List, Dict, Tuple, Set
from datetime import datetime
import hashlib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table

try:
    from utils.supabase_manager_unified import UnifiedSupabaseManager
except ImportError:
    from supabase_manager_unified import UnifiedSupabaseManager

class ArticlePreprocessor:
    """기사 전처리 클래스"""
    
    def __init__(self):
        self.console = Console()
        self.supabase = UnifiedSupabaseManager()
        self.logger = logging.getLogger(__name__)
        
        # TF-IDF 벡터라이저 초기화
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words=None,  # 한국어는 별도 처리 필요
            ngram_range=(1, 2)
        )
        
        # 중복 제거 통계
        self.stats = {
            'total_articles': 0,
            'duplicate_url_media': 0,
            'duplicate_content_exact': 0,
            'duplicate_content_similar': 0,
            'short_content_removed': 0,
            'final_articles': 0
        }
    
    def preprocess_articles(self) -> bool:
        """기사 전처리 메인 함수"""
        if not self.supabase.is_connected():
            self.console.print("[red]Supabase에 연결되지 않았습니다.[/red]")
            return False
        
        try:
            self.console.print(Panel("🔍 기사 전처리 시작", style="blue"))
            
            # 1. 모든 기사 조회
            articles = self._fetch_all_articles()
            if not articles:
                self.console.print("[yellow]처리할 기사가 없습니다.[/yellow]")
                return True
            
            self.stats['total_articles'] = len(articles)
            self.console.print(f"[green]총 {len(articles)}개 기사 조회 완료[/green]")
            
            # 2. URL + media_id 중복 제거
            articles = self._remove_url_media_duplicates(articles)
            
            # 3. 같은 언론사 내 content 중복 제거
            articles = self._remove_content_duplicates(articles)
            
            # 4. 짧은 기사 제거
            articles = self._remove_short_articles(articles)
            
            # 5. 날짜 형식 통일
            articles = self._normalize_dates(articles)
            
            # 6. 최종 결과를 Supabase에 반영
            success = self._update_supabase(articles)
            
            # 7. 결과 출력
            self._display_results()
            
            return success
            
        except Exception as e:
            self.logger.error(f"전처리 중 오류 발생: {str(e)}")
            self.console.print(f"[red]전처리 실패: {str(e)}[/red]")
            return False
    
    def _fetch_all_articles(self) -> List[Dict]:
        """모든 기사 조회"""
        try:
            result = self.supabase.client.table('articles').select('*').execute()
            return result.data if result.data else []
        except Exception as e:
            self.logger.error(f"기사 조회 실패: {str(e)}")
            return []
    
    def _remove_url_media_duplicates(self, articles: List[Dict]) -> List[Dict]:
        """URL + media_id 중복 제거"""
        self.console.print("[blue]URL + media_id 중복 제거 중...[/blue]")
        
        seen = set()
        unique_articles = []
        
        for article in articles:
            url = article.get('url', '')
            media_id = article.get('media_id')
            
            if not url or media_id is None:
                continue
                
            key = (url, media_id)
            if key not in seen:
                seen.add(key)
                unique_articles.append(article)
            else:
                self.stats['duplicate_url_media'] += 1
        
        self.console.print(f"[green]URL 중복 제거 완료: {self.stats['duplicate_url_media']}개 제거[/green]")
        return unique_articles
    
    def _remove_content_duplicates(self, articles: List[Dict]) -> List[Dict]:
        """같은 언론사 내 content 중복 제거"""
        self.console.print("[blue]Content 중복 제거 중...[/blue]")
        
        # 언론사별로 그룹화
        media_groups = {}
        for article in articles:
            media_id = article.get('media_id')
            if media_id is not None:
                if media_id not in media_groups:
                    media_groups[media_id] = []
                media_groups[media_id].append(article)
        
        unique_articles = []
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=self.console
        ) as progress:
            task = progress.add_task("언론사별 중복 제거...", total=len(media_groups))
            
            for media_id, media_articles in media_groups.items():
                progress.update(task, description=f"언론사 {media_id} 처리 중...")
                
                # 완전히 동일한 content 제거
                content_hash_map = {}
                for article in media_articles:
                    content = article.get('content', '')
                    if not content:
                        continue
                    
                    content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
                    if content_hash not in content_hash_map:
                        content_hash_map[content_hash] = article
                    else:
                        self.stats['duplicate_content_exact'] += 1
                
                # 유사도 기반 중복 제거
                similar_articles = self._remove_similar_content(list(content_hash_map.values()))
                unique_articles.extend(similar_articles)
                
                progress.advance(task)
        
        self.console.print(f"[green]Content 중복 제거 완료: 정확 중복 {self.stats['duplicate_content_exact']}개, 유사 중복 {self.stats['duplicate_content_similar']}개 제거[/green]")
        return unique_articles
    
    def _remove_similar_content(self, articles: List[Dict]) -> List[Dict]:
        """유사도 기반 중복 제거 (같은 언론사 내에서만)"""
        if len(articles) <= 1:
            return articles
        
        try:
            # TF-IDF 벡터화
            contents = [article.get('content', '') for article in articles]
            tfidf_matrix = self.vectorizer.fit_transform(contents)
            
            # 코사인 유사도 계산
            similarity_matrix = cosine_similarity(tfidf_matrix)
            
            # 유사도가 0.95 이상인 쌍 찾기
            to_remove = set()
            
            for i in range(len(similarity_matrix)):
                for j in range(i + 1, len(similarity_matrix)):
                    if similarity_matrix[i][j] >= 0.95:
                        # 더 짧은 기사나 더 늦게 발행된 기사를 제거 대상으로 선택
                        article_i = articles[i]
                        article_j = articles[j]
                        
                        # 발행일 비교
                        date_i = self._parse_date(article_i.get('published_at'))
                        date_j = self._parse_date(article_j.get('published_at'))
                        
                        if date_i and date_j:
                            if date_i >= date_j:  # 더 늦거나 같은 시간의 기사 제거
                                to_remove.add(j)
                            else:
                                to_remove.add(i)
                        else:
                            # 발행일이 없으면 더 짧은 기사 제거
                            if len(article_i.get('content', '')) <= len(article_j.get('content', '')):
                                to_remove.add(i)
                            else:
                                to_remove.add(j)
            
            # 제거 대상이 아닌 기사들만 반환
            unique_articles = [articles[i] for i in range(len(articles)) if i not in to_remove]
            self.stats['duplicate_content_similar'] += len(articles) - len(unique_articles)
            
            return unique_articles
            
        except Exception as e:
            self.logger.error(f"유사도 계산 중 오류: {str(e)}")
            return articles
    
    def _remove_short_articles(self, articles: List[Dict]) -> List[Dict]:
        """짧은 기사 제거 (본문 길이 < 50자)"""
        self.console.print("[blue]짧은 기사 제거 중...[/blue]")
        
        filtered_articles = []
        for article in articles:
            content = article.get('content', '')
            if len(content) >= 50:
                filtered_articles.append(article)
            else:
                self.stats['short_content_removed'] += 1
        
        self.console.print(f"[green]짧은 기사 제거 완료: {self.stats['short_content_removed']}개 제거[/green]")
        return filtered_articles
    
    def _normalize_dates(self, articles: List[Dict]) -> List[Dict]:
        """날짜 형식을 YYYY-MM-DD HH:MM:SS로 통일"""
        self.console.print("[blue]날짜 형식 통일 중...[/blue]")
        
        for article in articles:
            published_at = article.get('published_at')
            if published_at:
                normalized_date = self._normalize_date(published_at)
                if normalized_date:
                    article['published_at'] = normalized_date
        
        self.console.print("[green]날짜 형식 통일 완료[/green]")
        return articles
    
    def _normalize_date(self, date_value) -> str:
        """날짜 값을 표준 형식으로 변환"""
        if isinstance(date_value, str):
            # 다양한 날짜 형식 처리
            try:
                # ISO 형식
                if 'T' in date_value:
                    dt = datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                # 일반적인 한국 날짜 형식들
                elif '-' in date_value:
                    if len(date_value.split('-')) == 3:
                        if ':' in date_value:
                            dt = datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S')
                        else:
                            dt = datetime.strptime(date_value, '%Y-%m-%d')
                    else:
                        return date_value
                else:
                    return date_value
                
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                return date_value
        elif hasattr(date_value, 'strftime'):
            # datetime 객체
            return date_value.strftime('%Y-%m-%d %H:%M:%S')
        
        return str(date_value)
    
    def _parse_date(self, date_value) -> datetime:
        """날짜 값을 datetime 객체로 파싱"""
        if isinstance(date_value, str):
            try:
                if 'T' in date_value:
                    return datetime.fromisoformat(date_value.replace('Z', '+00:00'))
                elif '-' in date_value and ':' in date_value:
                    return datetime.strptime(date_value, '%Y-%m-%d %H:%M:%S')
                elif '-' in date_value:
                    return datetime.strptime(date_value, '%Y-%m-%d')
            except:
                pass
        elif hasattr(date_value, 'strftime'):
            return date_value
        
        return None
    
    def _update_supabase(self, articles: List[Dict]) -> bool:
        """전처리된 결과를 Supabase에 반영"""
        self.console.print("[blue]Supabase 업데이트 중...[/blue]")
        
        try:
            # 기존 테이블 비우기 (모든 레코드 삭제)
            # Supabase에서는 WHERE 절이 필요하므로 항상 참인 조건 사용
            self.supabase.client.table('articles').delete().gte('id', 0).execute()
            
            # 새로운 데이터 삽입
            if articles:
                result = self.supabase.client.table('articles').insert(articles).execute()
                if result.data:
                    self.stats['final_articles'] = len(result.data)
                    self.console.print(f"[green]Supabase 업데이트 완료: {len(result.data)}개 기사 저장[/green]")
                    return True
            
            self.console.print("[yellow]저장할 기사가 없습니다.[/yellow]")
            return True
            
        except Exception as e:
            self.logger.error(f"Supabase 업데이트 실패: {str(e)}")
            self.console.print(f"[red]Supabase 업데이트 실패: {str(e)}[/red]")
            return False
    
    def _display_results(self):
        """전처리 결과 출력"""
        self.console.print(Panel("📊 전처리 결과", style="green"))
        
        table = Table(title="전처리 통계")
        table.add_column("항목", style="cyan")
        table.add_column("수량", style="magenta")
        
        table.add_row("전체 기사", str(self.stats['total_articles']))
        table.add_row("URL+미디어 중복 제거", str(self.stats['duplicate_url_media']))
        table.add_row("정확한 내용 중복 제거", str(self.stats['duplicate_content_exact']))
        table.add_row("유사 내용 중복 제거", str(self.stats['duplicate_content_similar']))
        table.add_row("짧은 기사 제거", str(self.stats['short_content_removed']))
        table.add_row("최종 기사", str(self.stats['final_articles']))
        
        self.console.print(table)
        
        # 요약 정보
        total_removed = (
            self.stats['duplicate_url_media'] + 
            self.stats['duplicate_content_exact'] + 
            self.stats['duplicate_content_similar'] + 
            self.stats['short_content_removed']
        )
        
        removal_rate = (total_removed / self.stats['total_articles']) * 100 if self.stats['total_articles'] > 0 else 0
        
        self.console.print(f"\n[green]총 {total_removed}개 기사 제거 ({removal_rate:.1f}%)[/green]")
        self.console.print(f"[green]데이터 품질 향상 완료![/green]")


def main():
    """메인 실행 함수"""
    preprocessor = ArticlePreprocessor()
    success = preprocessor.preprocess_articles()
    
    if success:
        print("\n✅ 전처리가 성공적으로 완료되었습니다!")
    else:
        print("\n❌ 전처리 중 오류가 발생했습니다.")


if __name__ == "__main__":
    main()
