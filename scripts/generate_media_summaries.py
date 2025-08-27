#!/usr/bin/env python3
"""
Media Summaries 생성 스크립트

각 클러스터(이슈)의 언론사별 보도 경향을 분석하고 OpenAI GPT-4o-mini를 사용하여 
의미있는 언론사별 요약을 생성하여 media_summaries 테이블에 저장합니다.
"""

import asyncio
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

# utils 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.supabase_manager_unified import UnifiedSupabaseManager


class MediaSummariesGenerator:
    def __init__(self):
        self.sm = UnifiedSupabaseManager()
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        
    async def generate_media_summaries(self):
        """모든 클러스터에 대해 Media Summaries를 생성합니다."""
        print("🚀 Media Summaries 생성 시작")
        print("=" * 60)
        
        try:
            # 기사, 클러스터, 언론사 정보 로드
            articles_result = self.sm.client.table('articles').select('*').execute()
            issues_result = self.sm.client.table('issues').select('*').gt('id', 1).execute()
            media_outlets_result = self.sm.client.table('media_outlets').select('*').execute()
            
            if not articles_result.data or not issues_result.data or not media_outlets_result.data:
                print("❌ 기사, 클러스터 또는 언론사 데이터를 찾을 수 없습니다.")
                return
            
            articles = articles_result.data
            issues = issues_result.data
            media_outlets = media_outlets_result.data
            
            # 언론사 ID를 이름으로 매핑
            media_id_to_name = {media['id']: media['name'] for media in media_outlets}
            
            print(f"📊 {len(articles)}개 기사, {len(issues)}개 클러스터, {len(media_outlets)}개 언론사 로드 완료\n")
            
            # 각 클러스터에 대해 Media Summaries 생성
            for issue in issues:
                cluster_id = issue['id']
                print(f"📊 클러스터 {cluster_id} Media Summaries 생성 중...")
                
                # 해당 클러스터의 기사들 수집
                cluster_articles = [article for article in articles if article.get('issue_id') == cluster_id]
                
                if not cluster_articles:
                    print(f"⚠️ 클러스터 {cluster_id}: 기사가 없습니다.")
                    continue
                
                # 언론사별로 기사 그룹화
                media_articles = self._group_articles_by_media(cluster_articles)
                
                # 각 언론사별로 요약 생성
                for media_id, media_articles_list in media_articles.items():
                    if media_articles_list:
                        media_name = media_id_to_name.get(media_id, f"언론사_{media_id}")
                        print(f"   📰 {media_name} ({len(media_articles_list)}개 기사) 분석 중...")
                        
                        # Media Summary 생성
                        media_summary = await self._generate_media_summary(cluster_id, media_id, media_articles_list, media_name)
                        
                        # 데이터베이스에 저장
                        self._save_media_summary(cluster_id, media_id, media_summary)
                
                print()
            
            print("✅ Media Summaries 생성 완료!")
            print("\n🎉 모든 Media Summaries가 성공적으로 생성되었습니다!")
            
        except Exception as e:
            print(f"❌ Media Summaries 생성 중 오류 발생: {e}")
    
    def _group_articles_by_media(self, articles: List[Dict]) -> Dict[int, List[Dict]]:
        """기사들을 언론사별로 그룹화합니다."""
        media_articles = defaultdict(list)
        
        for article in articles:
            media_id = article.get('media_id')
            if media_id:
                media_articles[media_id].append(article)
        
        return dict(media_articles)
    
    async def _generate_media_summary(self, cluster_id: int, media_id: int, articles: List[Dict], media_name: str) -> str:
        """특정 언론사의 기사들을 분석하여 요약을 생성합니다."""
        try:
            # 기사 내용을 하나의 텍스트로 결합
            combined_content = self._combine_media_articles_content(articles, media_name)
            
            # OpenAI API 호출
            summary = await self._call_openai_api(combined_content, media_name)
            
            return summary
            
        except Exception as e:
            print(f"❌ 언론사 {media_name} 요약 생성 실패: {e}")
            return f"{media_name}의 보도 경향 분석 중..."
    
    def _combine_media_articles_content(self, articles: List[Dict], media_name: str) -> str:
        """특정 언론사의 기사들을 결합합니다."""
        combined = [f"**{media_name}의 기사들:**\n"]
        
        for i, article in enumerate(articles, 1):
            title = article.get('title', '')
            content = article.get('content', '')
            
            if title and content:
                combined.append(f"{i}. 제목: {title}")
                combined.append(f"   내용: {content[:300]}...")
                combined.append("")
        
        return "\n".join(combined)
    
    async def _call_openai_api(self, content: str, media_name: str) -> str:
        """OpenAI API를 호출하여 언론사별 요약을 수행합니다."""
        import httpx
        
        prompt = self._create_media_analysis_prompt(content, media_name)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": "당신은 한국 언론사의 보도 경향을 분석하는 전문가입니다. 각 언론사의 기사들을 분석하여 해당 언론사의 관점과 편향성을 정확하게 요약해주세요."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 1000,
                    "temperature": 0.3
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                result = response.json()
                content_text = result['choices'][0]['message']['content']
                return content_text
            else:
                print(f"❌ OpenAI API 호출 실패: {response.status_code}")
                return f"{media_name}의 보도 경향 분석 중..."
    
    def _create_media_analysis_prompt(self, content: str, media_name: str) -> str:
        """언론사별 분석을 위한 프롬프트를 생성합니다."""
        prompt = f"""
다음 {media_name}의 한국 정치 뉴스 기사들을 분석하여 이 언론사의 보도 경향을 요약해주세요.

**분석할 기사들:**
{content}

**요구사항:**
1. **보도 관점**: 이 언론사가 어떤 관점에서 기사를 작성했는지
2. **편향성**: 좌파/중도/우파 중 어느 쪽에 편향되어 있는지
3. **주요 키워드**: 자주 사용하는 키워드나 표현
4. **보도 톤**: 비판적/긍정적/중립적 중 어떤 톤으로 보도하는지
5. **전체적 특징**: 이 언론사의 보도 스타일과 특징

**출력 형식:**
{media_name}의 보도 경향을 간결하고 명확하게 요약해주세요. 
구체적인 예시와 함께 설명하고, 200자 이내로 작성해주세요.
"""
        return prompt
    
    def _save_media_summary(self, cluster_id: int, media_id: int, summary: str):
        """Media Summary를 media_summaries 테이블에 저장합니다."""
        try:
            # 기존 media_summary 삭제 (중복 방지)
            self.sm.client.table('media_summaries').delete().eq('issue_id', cluster_id).eq('media_id', media_id).execute()
            
            # 새로운 media_summary 삽입
            summary_data = {
                'issue_id': cluster_id,
                'media_id': media_id,
                'summary': summary
            }
            
            result = self.sm.client.table('media_summaries').insert(summary_data).execute()
            
            if result.data:
                print(f"     ✅ {media_id} 저장 완료")
            else:
                print(f"     ❌ {media_id} 저장 실패")
                
        except Exception as e:
            print(f"     ❌ {media_id} 저장 실패: {e}")


async def main():
    """메인 함수"""
    try:
        generator = MediaSummariesGenerator()
        await generator.generate_media_summaries()
    except Exception as e:
        print(f"❌ 메인 실행 중 오류 발생: {e}")


if __name__ == "__main__":
    asyncio.run(main())
