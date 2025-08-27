#!/usr/bin/env python3
"""
ELI5 (Explain Like I'm 5) 생성 스크립트

Issues 테이블의 각 이슈에 대해 5살 아이도 이해할 수 있게 
쉽게 설명하는 ELI5 필드를 생성합니다.
- 어려운 정치 용어를 쉽게 풀어씀
- 불렛 형태로 정리
- 전문용어도 쉬운 말로 설명
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


class ELI5Generator:
    def __init__(self):
        self.sm = UnifiedSupabaseManager()
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        
    async def generate_all_eli5_explanations(self):
        """모든 이슈에 대해 ELI5 설명을 생성합니다."""
        print("🚀 ELI5 (Explain Like I'm 5) 생성 시작")
        print("=" * 60)
        
        try:
            # Issues 테이블에서 데이터 로드
            issues_result = self.sm.client.table('issues').select('*').gt('id', 1).execute()
            
            if not issues_result.data:
                print("❌ 이슈 데이터를 찾을 수 없습니다.")
                return
            
            issues = issues_result.data
            print(f"📊 {len(issues)}개 이슈 로드 완료\n")
            
            # 각 이슈에 대해 ELI5 설명 생성
            for issue in issues:
                issue_id = issue['id']
                title = issue.get('title', '')
                subtitle = issue.get('subtitle', '')
                summary = issue.get('summary', '')
                
                if not title and not subtitle and not summary:
                    print(f"⚠️ 이슈 {issue_id}: 설명할 내용이 없습니다.")
                    continue
                
                print(f"📊 이슈 {issue_id} ELI5 생성 중...")
                print(f"   제목: {title[:50]}...")
                
                # OpenAI API를 사용하여 ELI5 설명 생성
                eli5_explanation = await self._generate_eli5_explanation(title, subtitle, summary, issue_id)
                
                if eli5_explanation:
                    # 데이터베이스 업데이트
                    self._update_issue_eli5(issue_id, eli5_explanation)
                    print(f"   ✅ ELI5 설명 생성 완료")
                else:
                    print(f"   ❌ 생성 실패")
                
                print()
            
            print("✅ 모든 ELI5 설명 생성 완료!")
            print("\n🎉 Issues 테이블의 ELI5 필드가 업데이트되었습니다!")
            
        except Exception as e:
            print(f"❌ ELI5 생성 중 오류 발생: {e}")
    
    async def _generate_eli5_explanation(self, title: str, subtitle: str, summary: str, issue_id: int) -> str:
        """이슈에 대해 ELI5 설명을 생성합니다."""
        try:
            import httpx
            
            prompt = self._create_eli5_prompt(title, subtitle, summary)
            
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
                                "content": "당신은 복잡한 정치 이슈를 5살 아이도 이해할 수 있게 쉽게 설명하는 전문가입니다. 어려운 용어는 쉬운 말로 바꾸고, 구체적인 예시를 들어 설명해주세요."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "max_tokens": 1500,
                        "temperature": 0.3
                    },
                    timeout=60.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    content_text = result['choices'][0]['message']['content']
                    return self._parse_eli5_response(content_text)
                else:
                    print(f"❌ OpenAI API 호출 실패: {response.status_code}")
                    return ""
            
        except Exception as e:
            print(f"❌ 이슈 {issue_id} ELI5 생성 실패: {e}")
            return ""
    
    def _create_eli5_prompt(self, title: str, subtitle: str, summary: str) -> str:
        """ELI5 생성을 위한 프롬프트를 생성합니다."""
        prompt = f"""
다음 한국 정치 이슈를 5살 아이도 이해할 수 있게 쉽게 설명해주세요.

**이슈 정보:**
제목: {title}
부제목: {subtitle}
요약: {summary}

**요구사항:**
1. **정말 쉽게 설명**: 5살 아이도 이해할 수 있는 수준으로
2. **어려운 용어 풀어쓰기**: 정치 용어, 전문 용어를 일상적인 말로 바꾸기
3. **구체적인 예시**: 비유나 예시를 들어 설명하기
4. **불렛 형태**: 핵심 내용을 불렛 포인트로 정리
5. **한국어로**: 한국어로 자연스럽게 작성

**출력 형식:**
🎯 **이 이슈가 뭔가요?**
[아주 간단한 한 문장 설명]

🔍 **자세히 설명하면:**
• [첫 번째 핵심 내용 - 쉬운 말로]
• [두 번째 핵심 내용 - 쉬운 말로]
• [세 번째 핵심 내용 - 쉬운 말로]
• [네 번째 핵심 내용 - 쉬운 말로]
• [다섯 번째 핵심 내용 - 쉬운 말로]

💡 **쉽게 비유하면:**
[일상생활의 예시나 비유로 설명]

⚠️ **우리에게 어떤 영향이 있나요?**
[일반 시민들에게 미치는 영향]
"""
        return prompt
    
    def _parse_eli5_response(self, response_text: str) -> str:
        """AI 응답을 파싱하여 ELI5 형태로 정리합니다."""
        try:
            # 전체 응답을 그대로 반환 (이미 구조화되어 있음)
            return response_text.strip()
            
        except Exception as e:
            print(f"❌ ELI5 응답 파싱 실패: {e}")
            return response_text
    
    def _update_issue_eli5(self, issue_id: int, eli5_explanation: str):
        """Issues 테이블의 eli5 필드를 업데이트합니다."""
        try:
            update_data = {
                'eli5': eli5_explanation,
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
        generator = ELI5Generator()
        await generator.generate_all_eli5_explanations()
    except Exception as e:
        print(f"❌ 메인 실행 중 오류 발생: {e}")


if __name__ == "__main__":
    asyncio.run(main())
