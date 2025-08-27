#!/usr/bin/env python3
"""
Common Points 생성 스크립트
- 각 클러스터의 기사들을 분석하여 공통점 도출
- OpenAI GPT-4를 사용하여 의미있는 Common Points 생성
"""

import sys
import os
import json
import asyncio
from typing import Dict, List, Tuple
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.supabase_manager_unified import UnifiedSupabaseManager
import openai


class CommonPointsGenerator:
    def __init__(self):
        self.sm = UnifiedSupabaseManager()
        self.client = openai.AsyncOpenAI()
        
    async def generate_all_common_points(self):
        """모든 클러스터에 대해 Common Points를 생성합니다."""
        print("🔍 Common Points 생성 시작")
        
        # 1. 기사와 클러스터 정보 로드
        articles, cluster_data = self._load_data()
        if not articles or not cluster_data:
            print("❌ 데이터 로드 실패")
            return False
            
        # 2. 각 클러스터별로 Common Points 생성
        for cluster_id, cluster_info in cluster_data.items():
            print(f"\n📊 클러스터 {cluster_id} Common Points 생성 중...")
            
            # 클러스터에 속한 기사들
            cluster_articles = [a for a in articles if a['issue_id'] == cluster_id]
            if not cluster_articles:
                continue
                
            # Common Points 생성
            common_points = await self._generate_cluster_common_points(cluster_articles, cluster_id)
            if common_points:
                # Issues 테이블에 common_points 저장
                self._save_common_points(cluster_id, common_points)
                
        print("\n✅ Common Points 생성 완료!")
        return True
        
    def _load_data(self) -> Tuple[List[Dict], Dict]:
        """기사와 클러스터 데이터를 로드합니다."""
        try:
            # 기사 데이터 로드
            articles_result = self.sm.client.table('articles').select('*').execute()
            articles = articles_result.data
            
            # 클러스터 데이터 로드 (ID 1 제외 - 기본 이슈)
            issues_result = self.sm.client.table('issues').select('*').gt('id', 1).execute()
            cluster_data = {issue['id']: issue for issue in issues_result.data}
            
            print(f"📊 {len(articles)}개 기사, {len(cluster_data)}개 클러스터 로드 완료")
            return articles, cluster_data
            
        except Exception as e:
            print(f"❌ 데이터 로드 실패: {e}")
            return [], {}
            
    async def _generate_cluster_common_points(self, articles: List[Dict], cluster_id: int) -> Dict:
        """클러스터의 Common Points를 생성합니다."""
        try:
            # 클러스터 내 기사들의 제목과 내용 수집
            titles = []
            contents = []
            
            for article in articles[:15]:  # 상위 15개 기사만 사용 (토큰 제한)
                title = article.get('title', '')
                content = article.get('content', '')
                if title and content:
                    titles.append(title)
                    # 내용은 150자로 제한
                    contents.append(content[:150] + "..." if len(content) > 150 else content)
                    
            if not titles:
                return None
                
            # 프롬프트 구성
            prompt = self._build_common_points_prompt(titles, contents, cluster_id)
            
            # OpenAI API 호출
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 한국 정치 뉴스 기사들을 분석하여 클러스터의 공통점을 도출하는 전문가입니다. 각 클러스터의 기사들을 분석하여 핵심 공통점을 찾아내고, 이를 체계적으로 정리해주세요."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=800
            )
            
            # 응답 파싱
            content_text = response.choices[0].message.content
            parsed_points = self._parse_common_points_response(content_text)
            
            return parsed_points
            
        except Exception as e:
            print(f"❌ Common Points 생성 실패: {e}")
            return None
            
    def _build_common_points_prompt(self, titles: List[str], contents: List[str], cluster_id: int) -> str:
        """Common Points 생성을 위한 프롬프트를 구성합니다."""
        prompt = f"""
다음은 클러스터 {cluster_id}에 속한 정치 뉴스 기사들입니다. 이 기사들을 분석하여 다음 형식으로 Common Points를 도출해주세요:

**주요 주제 (Main Topics)**: 이 클러스터를 대표하는 3-5개의 핵심 주제
**공통 키워드 (Common Keywords)**: 기사들에서 자주 등장하는 8-10개의 중요 키워드
**핵심 이슈 (Core Issues)**: 클러스터의 중심이 되는 2-3개의 주요 이슈
**정치적 맥락 (Political Context)**: 이 클러스터가 반영하는 정치적 상황이나 맥락
**언론사 편향성 (Media Bias Patterns)**: 클러스터 내 언론사들의 편향성 패턴

기사 제목들:
{chr(10).join([f"- {title}" for title in titles[:8]])}

기사 내용 샘플:
{chr(10).join([f"- {content}" for content in contents[:5]])}

응답 형식:
주요 주제: [주제1, 주제2, 주제3...]
공통 키워드: [키워드1, 키워드2, 키워드3...]
핵심 이슈: [이슈1, 이슈2, 이슈3...]
정치적 맥락: [맥락 설명]
언론사 편향성: [편향성 패턴 설명]
"""
        return prompt
        
    def _parse_common_points_response(self, response_text: str) -> Dict:
        """AI 응답을 파싱합니다."""
        try:
            content = {}
            
            # **주요 주제** 패턴 찾기
            if '**주요 주제**' in response_text:
                start = response_text.find('**주요 주제**') + len('**주요 주제**')
                start = response_text.find(':', start) + 1
                end = response_text.find('**', start)
                if end == -1:
                    end = response_text.find('\n', start)
                if end == -1:
                    end = len(response_text)
                topics_text = response_text[start:end].strip()
                # [주제1, 주제2, ...] 형태에서 추출
                if '[' in topics_text and ']' in topics_text:
                    topics_content = topics_text[topics_text.find('[')+1:topics_text.find(']')]
                    content['main_topics'] = [topic.strip() for topic in topics_content.split(',')]
                else:
                    content['main_topics'] = [topics_text.strip()]
            
            # **공통 키워드** 패턴 찾기
            if '**공통 키워드**' in response_text:
                start = response_text.find('**공통 키워드**') + len('**공통 키워드**')
                start = response_text.find(':', start) + 1
                end = response_text.find('**', start)
                if end == -1:
                    end = response_text.find('\n', start)
                if end == -1:
                    end = len(response_text)
                keywords_text = response_text[start:end].strip()
                if '[' in keywords_text and ']' in keywords_text:
                    keywords_content = keywords_text[keywords_text.find('[')+1:keywords_text.find(']')]
                    content['common_keywords'] = [kw.strip() for kw in keywords_content.split(',')]
                else:
                    content['common_keywords'] = [keywords_text.strip()]
            
            # **핵심 이슈** 패턴 찾기
            if '**핵심 이슈**' in response_text:
                start = response_text.find('**핵심 이슈**') + len('**핵심 이슈**')
                start = response_text.find(':', start) + 1
                end = response_text.find('**', start)
                if end == -1:
                    end = response_text.find('\n', start)
                if end == -1:
                    end = len(response_text)
                issues_text = response_text[start:end].strip()
                if '[' in issues_text and ']' in issues_text:
                    issues_content = issues_text[issues_text.find('[')+1:issues_text.find(']')]
                    content['core_issues'] = [issue.strip() for issue in issues_content.split(',')]
                else:
                    content['core_issues'] = [issue.strip()]
            
            # **정치적 맥락** 패턴 찾기
            if '**정치적 맥락**' in response_text:
                start = response_text.find('**정치적 맥락**') + len('**정치적 맥락**')
                start = response_text.find(':', start) + 1
                end = response_text.find('**', start)
                if end == -1:
                    end = response_text.find('\n', start)
                if end == -1:
                    end = len(response_text)
                context_text = response_text[start:end].strip()
                content['political_context'] = context_text
            
            # **언론사 편향성** 패턴 찾기
            if '**언론사 편향성**' in response_text:
                start = response_text.find('**언론사 편향성**') + len('**언론사 편향성**')
                start = response_text.find(':', start) + 1
                end = response_text.find('**', start)
                if end == -1:
                    end = response_text.find('\n', start)
                if end == -1:
                    end = len(response_text)
                bias_text = response_text[start:end].strip()
                content['media_bias_patterns'] = bias_text
            
            # 필수 필드 확인
            required_fields = ['main_topics', 'common_keywords', 'core_issues', 'political_context', 'media_bias_patterns']
            if not all(field in content for field in required_fields):
                print(f"⚠️ Common Points 파싱 실패, 기본값 사용: {response_text[:100]}...")
                return {
                    'main_topics': ['주제 분석 중'],
                    'common_keywords': ['키워드 분석 중'],
                    'core_issues': ['이슈 분석 중'],
                    'political_context': '정치적 맥락 분석 중',
                    'media_bias_patterns': '편향성 패턴 분석 중'
                }
                
            return content
            
        except Exception as e:
            print(f"❌ Common Points 파싱 실패: {e}")
            return {
                'main_topics': ['주제 분석 중'],
                'common_keywords': ['키워드 분석 중'],
                'core_issues': ['이슈 분석 중'],
                'political_context': '정치적 맥락 분석 중',
                'media_bias_patterns': '편향성 패턴 분석 중'
            }
            
    def _save_common_points(self, cluster_id: int, common_points: Dict):
        """Common Points를 common_points 테이블에 저장합니다."""
        try:
            # 기존 common_points 삭제 (이슈별로 새로 생성)
            self.sm.client.table('common_points').delete().eq('issue_id', cluster_id).execute()
            
            # 새로운 common_points 삽입
            points_to_insert = []
            
            # 주요 주제
            for topic in common_points.get('main_topics', []):
                points_to_insert.append({
                    'issue_id': cluster_id,
                    'point': f"주요 주제: {topic}"
                })
            
            # 공통 키워드
            for keyword in common_points.get('common_keywords', []):
                points_to_insert.append({
                    'issue_id': cluster_id,
                    'point': f"공통 키워드: {keyword}"
                })
            
            # 핵심 이슈
            for issue in common_points.get('core_issues', []):
                points_to_insert.append({
                    'issue_id': cluster_id,
                    'point': f"핵심 이슈: {issue}"
                })
            
            # 정치적 맥락
            political_context = common_points.get('political_context', '')
            if political_context:
                points_to_insert.append({
                    'issue_id': cluster_id,
                    'point': f"정치적 맥락: {political_context}"
                })
            
            # 언론사 편향성
            media_bias = common_points.get('media_bias_patterns', '')
            if media_bias:
                points_to_insert.append({
                    'issue_id': cluster_id,
                    'point': f"언론사 편향성: {media_bias}"
                })
            
            # common_points 테이블에 삽입
            if points_to_insert:
                result = self.sm.client.table('common_points').insert(points_to_insert).execute()
                
                if result.data:
                    print(f"✅ 클러스터 {cluster_id} Common Points 저장 완료")
                    print(f"   주요 주제: {len(common_points.get('main_topics', []))}개")
                    print(f"   공통 키워드: {len(common_points.get('common_keywords', []))}개")
                    print(f"   핵심 이슈: {len(common_points.get('core_issues', []))}개")
                    print(f"   총 {len(points_to_insert)}개 포인트 저장")
                else:
                    print(f"❌ 클러스터 {cluster_id} 저장 실패")
            else:
                print(f"⚠️ 클러스터 {cluster_id}: 저장할 포인트가 없습니다")
                
        except Exception as e:
            print(f"❌ 클러스터 {cluster_id} 저장 실패: {e}")


async def main():
    """메인 실행 함수"""
    print("🚀 Common Points 생성 시작")
    print("=" * 60)
    
    generator = CommonPointsGenerator()
    success = await generator.generate_all_common_points()
    
    if success:
        print("\n🎉 모든 Common Points가 성공적으로 생성되었습니다!")
    else:
        print("\n❌ 일부 작업이 실패했습니다.")


if __name__ == "__main__":
    asyncio.run(main())
