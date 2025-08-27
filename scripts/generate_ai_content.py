#!/usr/bin/env python3
"""
AI 기반 Issues 콘텐츠 생성 스크립트
- OpenAI GPT-4를 사용하여 각 클러스터의 title, subtitle, summary 생성
- 클러스터 내 기사들의 내용을 분석하여 의미있는 콘텐츠 생성
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


class AIContentGenerator:
    def __init__(self):
        self.sm = UnifiedSupabaseManager()
        self.client = openai.AsyncOpenAI()
        
    async def generate_all_content(self):
        """모든 클러스터에 대해 AI 콘텐츠를 생성합니다."""
        print("🤖 AI 기반 Issues 콘텐츠 생성 시작")
        
        # 1. 기사와 클러스터 정보 로드
        articles, cluster_data = self._load_data()
        if not articles or not cluster_data:
            print("❌ 데이터 로드 실패")
            return False
            
        # 2. 각 클러스터별로 AI 콘텐츠 생성
        for cluster_id, cluster_info in cluster_data.items():
            print(f"\n📊 클러스터 {cluster_id} AI 콘텐츠 생성 중...")
            
            # 클러스터에 속한 기사들
            cluster_articles = [a for a in articles if a['issue_id'] == cluster_id]
            if not cluster_articles:
                continue
                
            # AI 콘텐츠 생성
            ai_content = await self._generate_cluster_content(cluster_articles, cluster_id)
            if ai_content:
                # Issues 테이블 업데이트
                self._update_issue_content(cluster_id, ai_content)
                
        print("\n✅ AI 콘텐츠 생성 완료!")
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
            
    async def _generate_cluster_content(self, articles: List[Dict], cluster_id: int) -> Dict:
        """클러스터의 AI 콘텐츠를 생성합니다."""
        try:
            # 클러스터 내 기사들의 제목과 내용 수집
            titles = []
            contents = []
            
            for article in articles[:20]:  # 상위 20개 기사만 사용 (토큰 제한)
                title = article.get('title', '')
                content = article.get('content', '')
                if title and content:
                    titles.append(title)
                    # 내용은 200자로 제한
                    contents.append(content[:200] + "..." if len(content) > 200 else content)
                    
            if not titles:
                return None
                
            # 프롬프트 구성
            prompt = self._build_prompt(titles, contents, cluster_id)
            
            # OpenAI API 호출
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 한국 정치 뉴스 기사들을 분석하여 핵심 이슈를 파악하고 요약하는 전문가입니다. 각 클러스터의 기사들을 분석하여 의미있는 제목, 부제목, 요약을 생성해주세요."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=500
            )
            
            # 응답 파싱
            content_text = response.choices[0].message.content
            parsed_content = self._parse_ai_response(content_text)
            
            return parsed_content
            
        except Exception as e:
            print(f"❌ AI 콘텐츠 생성 실패: {e}")
            return None
            
    def _build_prompt(self, titles: List[str], contents: List[str], cluster_id: int) -> str:
        """AI 프롬프트를 구성합니다."""
        prompt = f"""
다음은 클러스터 {cluster_id}에 속한 정치 뉴스 기사들입니다. 이 기사들을 분석하여 다음 형식으로 응답해주세요:

**제목 (Title)**: 이 클러스터를 대표하는 핵심 이슈나 사건을 담은 간결한 제목
**부제목 (Subtitle)**: 클러스터의 주요 특징이나 관점을 요약한 부제목
**요약 (Summary)**: 클러스터 내 기사들의 핵심 내용을 종합한 2-3문장 요약

기사 제목들:
{chr(10).join([f"- {title}" for title in titles[:10]])}

기사 내용 샘플:
{chr(10).join([f"- {content}" for content in contents[:5]])}

응답 형식:
제목: [핵심 이슈 제목]
부제목: [주요 특징 부제목]
요약: [2-3문장 요약]
"""
        return prompt
        
    def _parse_ai_response(self, response_text: str) -> Dict:
        """AI 응답을 파싱합니다."""
        try:
            # AI 응답에서 **제목**, **부제목**, **요약** 패턴 찾기
            content = {}
            
            # 제목 추출
            if '**제목 (Title)**:' in response_text:
                title_start = response_text.find('**제목 (Title)**:') + len('**제목 (Title)**:')
                title_end = response_text.find('**', title_start)
                if title_end == -1:
                    title_end = response_text.find('\n', title_start)
                if title_end == -1:
                    title_end = len(response_text)
                content['title'] = response_text[title_start:title_end].strip()
            
            # 부제목 추출
            if '**부제목 (Subtitle)**:' in response_text:
                subtitle_start = response_text.find('**부제목 (Subtitle)**:') + len('**부제목 (Subtitle)**:')
                subtitle_end = response_text.find('**', subtitle_start)
                if subtitle_end == -1:
                    subtitle_end = response_text.find('\n', subtitle_start)
                if subtitle_end == -1:
                    subtitle_end = len(response_text)
                content['subtitle'] = response_text[subtitle_start:subtitle_end].strip()
            
            # 요약 추출
            if '**요약 (Summary)**:' in response_text:
                summary_start = response_text.find('**요약 (Summary)**:') + len('**요약 (Summary)**:')
                summary_end = response_text.find('**', summary_start)
                if summary_end == -1:
                    summary_end = len(response_text)
                content['summary'] = response_text[summary_start:summary_end].strip()
            
            # 필수 필드 확인
            required_fields = ['title', 'subtitle', 'summary']
            if not all(field in content for field in required_fields):
                print(f"⚠️ AI 응답 파싱 실패, 기본값 사용: {response_text[:100]}...")
                return {
                    'title': 'AI 생성 제목',
                    'subtitle': 'AI 생성 부제목', 
                    'summary': 'AI 생성 요약'
                }
                
            return content
            
        except Exception as e:
            print(f"❌ AI 응답 파싱 실패: {e}")
            return {
                'title': 'AI 생성 제목',
                'subtitle': 'AI 생성 부제목',
                'summary': 'AI 생성 요약'
            }
            
    def _update_issue_content(self, cluster_id: int, ai_content: Dict):
        """Issues 테이블의 콘텐츠를 업데이트합니다."""
        try:
            update_data = {
                'title': ai_content['title'],
                'subtitle': ai_content['subtitle'],
                'summary': ai_content['summary'],
                'updated_at': datetime.now().isoformat()
            }
            
            result = self.sm.client.table('issues').update(update_data).eq('id', cluster_id).execute()
            
            if result.data:
                print(f"✅ 클러스터 {cluster_id} AI 콘텐츠 업데이트 완료")
                print(f"   제목: {ai_content['title']}")
                print(f"   부제목: {ai_content['subtitle']}")
                print(f"   요약: {ai_content['summary'][:100]}...")
            else:
                print(f"❌ 클러스터 {cluster_id} 업데이트 실패")
                
        except Exception as e:
            print(f"❌ 클러스터 {cluster_id} 업데이트 실패: {e}")


async def main():
    """메인 실행 함수"""
    print("🚀 AI 기반 Issues 콘텐츠 생성 시작")
    print("=" * 60)
    
    generator = AIContentGenerator()
    success = await generator.generate_all_content()
    
    if success:
        print("\n🎉 모든 AI 콘텐츠가 성공적으로 생성되었습니다!")
    else:
        print("\n❌ 일부 작업이 실패했습니다.")


if __name__ == "__main__":
    asyncio.run(main())
