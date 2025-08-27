#!/usr/bin/env python3
"""
Bias Summaries 생성 스크립트

각 클러스터(이슈)의 편향성을 분석하고 OpenAI GPT-4o-mini를 사용하여 
의미있는 편향성 요약을 생성하여 bias_summaries 테이블에 저장합니다.
"""

import asyncio
import os
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional

# utils 모듈 import를 위한 경로 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.supabase_manager_unified import UnifiedSupabaseManager


class BiasSummariesGenerator:
    def __init__(self):
        self.sm = UnifiedSupabaseManager()
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        
    async def generate_bias_summaries(self):
        """모든 클러스터에 대해 Bias Summaries를 생성합니다."""
        print("🚀 Bias Summaries 생성 시작")
        print("=" * 60)
        
        try:
            # 기사와 클러스터 정보 로드
            articles_result = self.sm.client.table('articles').select('*').execute()
            issues_result = self.sm.client.table('issues').select('*').gt('id', 1).execute()
            
            if not articles_result.data or not issues_result.data:
                print("❌ 기사 또는 클러스터 데이터를 찾을 수 없습니다.")
                return
            
            articles = articles_result.data
            issues = issues_result.data
            
            print(f"📊 {len(articles)}개 기사, {len(issues)}개 클러스터 로드 완료\n")
            
            # 각 클러스터에 대해 Bias Summaries 생성
            for issue in issues:
                cluster_id = issue['id']
                print(f"📊 클러스터 {cluster_id} Bias Summaries 생성 중...")
                
                # 해당 클러스터의 기사들 수집
                cluster_articles = [article for article in articles if article.get('issue_id') == cluster_id]
                
                if not cluster_articles:
                    print(f"⚠️ 클러스터 {cluster_id}: 기사가 없습니다.")
                    continue
                
                # Bias Summaries 생성
                bias_summaries = await self._generate_cluster_bias_summaries(cluster_id, cluster_articles)
                
                # 데이터베이스에 저장
                self._save_bias_summaries(cluster_id, bias_summaries)
                
                print()
            
            print("✅ Bias Summaries 생성 완료!")
            print("\n🎉 모든 Bias Summaries가 성공적으로 생성되었습니다!")
            
        except Exception as e:
            print(f"❌ Bias Summaries 생성 중 오류 발생: {e}")
    
    async def _generate_cluster_bias_summaries(self, cluster_id: int, articles: List[Dict]) -> List[Dict]:
        """특정 클러스터의 편향성 요약을 생성합니다."""
        try:
            # 기사 내용을 하나의 텍스트로 결합
            combined_content = self._combine_articles_content(articles)
            
            # OpenAI API 호출
            bias_summaries = await self._call_openai_api(combined_content, cluster_id)
            
            return bias_summaries
            
        except Exception as e:
            print(f"❌ 클러스터 {cluster_id} Bias Summaries 생성 실패: {e}")
            return []
    
    def _combine_articles_content(self, articles: List[Dict]) -> str:
        """기사들의 내용을 결합합니다."""
        combined = []
        
        for article in articles:
            title = article.get('title', '')
            content = article.get('content', '')
            media = article.get('media', '')
            
            if title and content:
                combined.append(f"제목: {title}\n내용: {content[:500]}...\n언론사: {media}\n")
        
        return "\n".join(combined)
    
    async def _call_openai_api(self, content: str, cluster_id: int) -> List[Dict]:
        """OpenAI API를 호출하여 편향성 분석을 수행합니다."""
        import httpx
        
        prompt = self._create_bias_analysis_prompt(content)
        
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
                            "content": "당신은 한국 정치 뉴스의 편향성을 분석하는 전문가입니다. 각 언론사의 편향성을 정확하게 분석하고 요약해주세요."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.3
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                result = response.json()
                content_text = result['choices'][0]['message']['content']
                return self._parse_bias_response(content_text)
            else:
                print(f"❌ OpenAI API 호출 실패: {response.status_code}")
                return []
    
    def _create_bias_analysis_prompt(self, content: str) -> str:
        """편향성 분석을 위한 프롬프트를 생성합니다."""
        prompt = f"""
다음 한국 정치 뉴스 기사들을 분석하여 편향성을 요약해주세요.

**분석할 기사들:**
{content}

**요구사항:**
1. **좌파 편향 (Left Bias)**: 진보적, 민주당 지지, 이재명 대통령 긍정적 보도
2. **중도 편향 (Center Bias)**: 균형잡힌, 객관적, 양쪽 모두 비판적/긍정적
3. **우파 편향 (Right Bias)**: 보수적, 국민의힘 지지, 윤석열 대통령 긍정적 보도

**출력 형식 (정확히 이 형식을 따라주세요):**
좌파 편향:
[좌파 편향이 드러나는 기사들의 구체적이고 의미있는 요약을 작성해주세요. 최소 50자 이상으로 작성해주세요.]

중도 편향:
[중도적 성향의 기사들의 구체적이고 의미있는 요약을 작성해주세요. 최소 50자 이상으로 작성해주세요.]

우파 편향:
[우파 편향이 드러나는 기사들의 구체적이고 의미있는 요약을 작성해주세요. 최소 50자 이상으로 작성해주세요.]

각 편향성 유형별로 구체적이고 의미있는 요약을 제공해주세요. 빈 내용이나 "1." 같은 의미없는 텍스트는 절대 사용하지 마세요.
"""
        return prompt
    
    def _parse_bias_response(self, response_text: str) -> List[Dict]:
        """AI 응답을 파싱합니다."""
        try:
            bias_summaries = []
            
            # 좌파 편향 추출 (마크다운 형식과 일반 형식 모두 지원)
            left_patterns = ['**좌파 편향:**', '좌파 편향:']
            left_summary = None
            for pattern in left_patterns:
                if pattern in response_text:
                    start = response_text.find(pattern) + len(pattern)
                    end = response_text.find('중도 편향:', start)
                    if end == -1:
                        end = response_text.find('우파 편향:', start)
                    if end == -1:
                        end = len(response_text)
                    left_summary = response_text[start:end].strip()
                    break
            
            # 중도 편향 추출
            center_patterns = ['**중도 편향:**', '중도 편향:']
            center_summary = None
            for pattern in center_patterns:
                if pattern in response_text:
                    start = response_text.find(pattern) + len(pattern)
                    end = response_text.find('우파 편향:', start)
                    if end == -1:
                        end = len(response_text)
                    center_summary = response_text[start:end].strip()
                    break
            
            # 우파 편향 추출
            right_patterns = ['**우파 편향:**', '우파 편향:']
            right_summary = None
            for pattern in right_patterns:
                if pattern in response_text:
                    start = response_text.find(pattern) + len(pattern)
                    end = len(response_text)
                    right_summary = response_text[start:end].strip()
                    break
            
            # 유효한 요약만 추가 (의미없는 텍스트 제외)
            if left_summary and len(left_summary.strip()) > 10 and not left_summary.strip().startswith(('1.', '-', '.')):
                bias_summaries.append({
                    'bias': 'Left',
                    'summary': left_summary
                })
            
            if center_summary and len(center_summary.strip()) > 10 and not center_summary.strip().startswith(('1.', '-', '.')):
                bias_summaries.append({
                    'bias': 'Center',
                    'summary': center_summary
                })
            
            if right_summary and len(right_summary.strip()) > 10 and not right_summary.strip().startswith(('1.', '-', '.')):
                bias_summaries.append({
                    'bias': 'Right',
                    'summary': right_summary
                })
            
            if not bias_summaries:
                print(f"⚠️ Bias 응답 파싱 실패, 기본값 사용: {response_text[:100]}...")
                bias_summaries = [
                    {'bias': 'Left', 'summary': '편향성 분석 중'},
                    {'bias': 'Center', 'summary': '편향성 분석 중'},
                    {'bias': 'Right', 'summary': '편향성 분석 중'}
                ]
            
            return bias_summaries
            
        except Exception as e:
            print(f"❌ Bias 응답 파싱 실패: {e}")
            return [
                {'bias': 'Left', 'summary': '편향성 분석 중'},
                {'bias': 'Center', 'summary': '편향성 분석 중'},
                {'bias': 'Right', 'summary': '편향성 분석 중'}
            ]
    
    def _save_bias_summaries(self, cluster_id: int, bias_summaries: List[Dict]):
        """Bias Summaries를 bias_summaries 테이블에 저장합니다."""
        try:
            # 기존 bias_summaries 삭제 (이슈별로 새로 생성)
            self.sm.client.table('bias_summaries').delete().eq('issue_id', cluster_id).execute()
            
            # 새로운 bias_summaries 삽입
            summaries_to_insert = []
            
            for bias_summary in bias_summaries:
                summaries_to_insert.append({
                    'issue_id': cluster_id,
                    'bias': bias_summary['bias'],
                    'summary': bias_summary['summary']
                })
            
            # bias_summaries 테이블에 삽입
            if summaries_to_insert:
                result = self.sm.client.table('bias_summaries').insert(summaries_to_insert).execute()
                
                if result.data:
                    print(f"✅ 클러스터 {cluster_id} Bias Summaries 저장 완료")
                    print(f"   편향성 유형: {len(summaries_to_insert)}개")
                    for summary in summaries_to_insert:
                        print(f"     - {summary['bias']}: {summary['summary'][:50]}...")
                else:
                    print(f"❌ 클러스터 {cluster_id} 저장 실패")
            else:
                print(f"⚠️ 클러스터 {cluster_id}: 저장할 편향성 요약이 없습니다")
                
        except Exception as e:
            print(f"❌ 클러스터 {cluster_id} 저장 실패: {e}")


async def main():
    """메인 함수"""
    try:
        generator = BiasSummariesGenerator()
        await generator.generate_bias_summaries()
    except Exception as e:
        print(f"❌ 메인 실행 중 오류 발생: {e}")


if __name__ == "__main__":
    asyncio.run(main())
