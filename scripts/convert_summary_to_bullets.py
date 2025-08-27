#!/usr/bin/env python3
"""
Issues Summary를 불렛 형태로 변환하는 스크립트

Issues 테이블의 summary 필드를 OpenAI GPT-4o-mini를 사용하여 
구조화된 불렛 포인트 형태로 변환합니다.
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


class SummaryBulletConverter:
    def __init__(self):
        self.sm = UnifiedSupabaseManager()
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        
    async def convert_all_summaries_to_bullets(self):
        """모든 이슈의 summary를 불렛 형태로 변환합니다."""
        print("🚀 Issues Summary를 불렛 형태로 변환 시작")
        print("=" * 60)
        
        try:
            # Issues 테이블에서 데이터 로드
            issues_result = self.sm.client.table('issues').select('*').gt('id', 1).execute()
            
            if not issues_result.data:
                print("❌ 이슈 데이터를 찾을 수 없습니다.")
                return
            
            issues = issues_result.data
            print(f"📊 {len(issues)}개 이슈 로드 완료\n")
            
            # 각 이슈의 summary를 불렛 형태로 변환
            for issue in issues:
                issue_id = issue['id']
                current_summary = issue.get('summary', '')
                
                if not current_summary or current_summary == '요약 없음':
                    print(f"⚠️ 이슈 {issue_id}: 변환할 summary가 없습니다.")
                    continue
                
                print(f"📊 이슈 {issue_id} Summary 변환 중...")
                print(f"   현재: {current_summary[:100]}...")
                
                # OpenAI API를 사용하여 불렛 형태로 변환
                bullet_summary = await self._convert_to_bullets(current_summary, issue_id)
                
                if bullet_summary:
                    # 데이터베이스 업데이트
                    self._update_issue_summary(issue_id, bullet_summary)
                    print(f"   ✅ 불렛 형태로 변환 완료")
                else:
                    print(f"   ❌ 변환 실패")
                
                print()
            
            print("✅ 모든 Summary 변환 완료!")
            print("\n🎉 Issues 테이블의 Summary가 불렛 형태로 업데이트되었습니다!")
            
        except Exception as e:
            print(f"❌ Summary 변환 중 오류 발생: {e}")
    
    async def _convert_to_bullets(self, summary: str, issue_id: int) -> str:
        """Summary를 불렛 형태로 변환합니다."""
        try:
            import httpx
            
            prompt = self._create_bullet_conversion_prompt(summary)
            
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
                                "content": "당신은 한국 정치 뉴스의 요약을 구조화된 불렛 포인트로 변환하는 전문가입니다. 핵심 내용을 명확하고 간결한 불렛 포인트로 정리해주세요."
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
                    return self._parse_bullet_response(content_text)
                else:
                    print(f"❌ OpenAI API 호출 실패: {response.status_code}")
                    return summary
            
        except Exception as e:
            print(f"❌ 이슈 {issue_id} 변환 실패: {e}")
            return summary
    
    def _create_bullet_conversion_prompt(self, summary: str) -> str:
        """불렛 변환을 위한 프롬프트를 생성합니다."""
        prompt = f"""
다음 한국 정치 뉴스 요약을 구조화된 불렛 포인트로 변환해주세요.

**원본 요약:**
{summary}

**요구사항:**
1. 핵심 내용을 5-8개의 불렛 포인트로 정리
2. 각 불렛 포인트는 명확하고 간결하게 작성
3. 중요한 정보를 우선순위에 따라 배치
4. 정치적 맥락과 영향력을 명확히 표현
5. 한국어로 작성

**출력 형식:**
• [첫 번째 핵심 내용]
• [두 번째 핵심 내용]
• [세 번째 핵심 내용]
• [네 번째 핵심 내용]
• [다섯 번째 핵심 내용]

각 불렛 포인트는 독립적이면서도 전체적인 맥락을 유지하도록 작성해주세요.
"""
        return prompt
    
    def _parse_bullet_response(self, response_text: str) -> str:
        """AI 응답을 파싱하여 불렛 형태로 정리합니다."""
        try:
            # 불렛 포인트 추출
            lines = response_text.strip().split('\n')
            bullet_points = []
            
            for line in lines:
                line = line.strip()
                if line.startswith('•') or line.startswith('-') or line.startswith('*'):
                    # 불렛 기호 제거하고 내용만 추출
                    content = line.lstrip('•-* ').strip()
                    if content:
                        bullet_points.append(f"• {content}")
                elif line and not line.startswith('**') and not line.startswith('출력 형식:'):
                    # 불렛 기호가 없어도 내용이 있으면 불렛 포인트로 추가
                    if len(line) > 10:  # 너무 짧은 줄은 제외
                        bullet_points.append(f"• {line}")
            
            if bullet_points:
                return '\n'.join(bullet_points)
            else:
                # 파싱 실패 시 원본 반환
                return response_text
            
        except Exception as e:
            print(f"❌ 불렛 응답 파싱 실패: {e}")
            return response_text
    
    def _update_issue_summary(self, issue_id: int, bullet_summary: str):
        """Issues 테이블의 summary를 업데이트합니다."""
        try:
            update_data = {
                'summary': bullet_summary,
                'updated_at': datetime.now().isoformat()
            }
            
            result = self.sm.client.table('issues').update(update_data).eq('id', issue_id).execute()
            
            if result.data:
                print(f"   ✅ 데이터베이스 업데이트 완료")
            else:
                print(f"   ❌ 데이터베이스 업데이트 실패")
                
        except Exception as e:
            print(f"   ❌ 데이터베이스 업데이트 실패: {e}")


async def main():
    """메인 함수"""
    try:
        converter = SummaryBulletConverter()
        await converter.convert_all_summaries_to_bullets()
    except Exception as e:
        print(f"❌ 메인 실행 중 오류 발생: {e}")


if __name__ == "__main__":
    asyncio.run(main())
