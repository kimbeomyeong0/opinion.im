#!/usr/bin/env python3
"""
JSON 데이터 구조 분석 스크립트
"""

import asyncio
import httpx
import re
import json
from bs4 import BeautifulSoup
from rich.console import Console

console = Console()

async def debug_json_structure():
    """JSON 데이터 구조 분석"""
    
    url = "https://www.chosun.com/politics/politics_general/2025/08/19/MX46I5KXANFQZICDOXZAUV3VMU/"
    
    console.print(f"🔍 URL: {url}")
    console.print("=" * 80)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            html = response.text
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # script 태그에서 JSON 데이터 찾기
        scripts = soup.find_all('script')
        
        for i, script in enumerate(scripts):
            if not script.string:
                continue
                
            script_content = script.string
            
            if 'content_elements' in script_content:
                console.print(f"🔍 Script[{i}]에서 content_elements 발견!")
                console.print(f"   길이: {len(script_content)}자")
                
                # JSON 시작과 끝 찾기
                start_idx = script_content.find('{')
                end_idx = script_content.rfind('}') + 1
                
                if start_idx != -1 and end_idx != -1:
                    json_str = script_content[start_idx:end_idx]
                    console.print(f"   JSON 문자열 길이: {len(json_str)}자")
                    
                    # JSON 파싱 시도
                    try:
                        data = json.loads(json_str)
                        console.print("✅ JSON 파싱 성공!")
                        
                        # 데이터 구조 분석
                        console.print("\n📊 JSON 데이터 구조:")
                        console.print(f"   최상위 키들: {list(data.keys())}")
                        
                        # content_elements 분석
                        if 'content_elements' in data:
                            content_elements = data['content_elements']
                            console.print(f"   content_elements 개수: {len(content_elements)}")
                            
                            if content_elements:
                                first_element = content_elements[0]
                                console.print(f"   첫 번째 요소 키들: {list(first_element.keys())}")
                                
                                # 본문 관련 필드 찾기
                                content_fields = ['content', 'body', 'text', 'description', 'article_body', 'full_text']
                                for field in content_fields:
                                    if field in first_element:
                                        field_value = first_element[field]
                                        console.print(f"   ✅ {field} 필드 발견: {type(field_value)}")
                                        
                                        if isinstance(field_value, str):
                                            console.print(f"      길이: {len(field_value)}자")
                                            console.print(f"      내용: {field_value[:200]}...")
                                        elif isinstance(field_value, dict):
                                            console.print(f"      키들: {list(field_value.keys())}")
                                            
                                            if 'basic' in field_value:
                                                basic_value = field_value['basic']
                                                if isinstance(basic_value, str):
                                                    console.print(f"      basic 길이: {len(basic_value)}자")
                                                    console.print(f"      basic 내용: {basic_value[:200]}...")
                        
                        # 다른 가능한 본문 필드들
                        for key, value in data.items():
                            if key in ['content', 'body', 'text', 'description', 'article_body', 'full_text']:
                                console.print(f"   🔍 {key} 필드 발견: {type(value)}")
                                
                                if isinstance(value, str) and len(value) > 100:
                                    console.print(f"      길이: {len(value)}자")
                                    console.print(f"      내용: {value[:200]}...")
                                elif isinstance(value, dict):
                                    console.print(f"      키들: {list(value.keys())}")
                        
                    except json.JSONDecodeError as e:
                        console.print(f"❌ JSON 파싱 실패: {str(e)}")
                        
                        # 부분적으로 파싱 시도
                        console.print("🔧 부분 파싱 시도...")
                        
                        # content_elements 부분만 추출
                        content_match = re.search(r'"content_elements"\s*:\s*\[(.*?)\]', json_str, re.DOTALL)
                        if content_match:
                            content_part = content_match.group(1)
                            console.print(f"   content_elements 부분 길이: {len(content_part)}자")
                            
                            # 개별 content 요소들 추출
                            content_items = re.findall(r'\{[^}]*"content"[^}]*\}', content_part)
                            console.print(f"   content 필드가 있는 요소들: {len(content_items)}개")
                            
                            for j, item in enumerate(content_items[:5]):  # 처음 5개만
                                console.print(f"     {j+1}. {item[:200]}...")
                                
                                # content 값 추출
                                content_value_match = re.search(r'"content"\s*:\s*"([^"]*)"', item)
                                if content_value_match:
                                    content_value = content_value_match.group(1)
                                    if content_value:
                                        console.print(f"        content: {content_value[:100]}...")
                                    else:
                                        console.print(f"        content: (비어있음)")
                        
                        # description 부분 추출
                        desc_matches = re.findall(r'"description"\s*:\s*\{[^}]*\}', json_str)
                        console.print(f"   description 필드들: {len(desc_matches)}개")
                        
                        for j, desc in enumerate(desc_matches[:3]):  # 처음 3개만
                            console.print(f"     {j+1}. {desc[:200]}...")
                            
                            # basic 값 추출
                            basic_match = re.search(r'"basic"\s*:\s*"([^"]*)"', desc)
                            if basic_match:
                                basic_value = basic_match.group(1)
                                if basic_value:
                                    console.print(f"        basic: {basic_value[:100]}...")
                                else:
                                    console.print(f"        basic: (비어있음)")
                        
                        # 본문으로 보이는 긴 텍스트 찾기
                        console.print(f"\n🔍 본문으로 보이는 긴 텍스트 검색:")
                        
                        # 100자 이상의 텍스트 찾기
                        long_texts = re.findall(r'"([^"]{100,})"', json_str)
                        console.print(f"   100자 이상 텍스트: {len(long_texts)}개")
                        
                        for j, text in enumerate(long_texts[:5]):  # 처음 5개만
                            console.print(f"     {j+1}. {text[:200]}...")
                        
                        # 특정 키워드가 포함된 텍스트 찾기
                        console.print(f"\n🔍 특정 키워드 검색:")
                        keywords = ['윤미향', '조국', '김호중', '이은해', '광복절', '특별사면']
                        
                        for keyword in keywords:
                            if keyword in json_str:
                                # 키워드 주변 텍스트 추출
                                keyword_matches = re.findall(f'.{{0,50}}{keyword}.{{0,50}}', json_str)
                                console.print(f"   ✅ '{keyword}' 발견: {len(keyword_matches)}개")
                                
                                for match in keyword_matches[:2]:  # 처음 2개만
                                    console.print(f"      - {match}")
                        
                else:
                    console.print("❌ JSON 시작/끝을 찾을 수 없습니다")
                
                break  # 첫 번째 발견된 script만 분석
        
    except Exception as e:
        console.print(f"❌ 오류 발생: {str(e)}")

if __name__ == "__main__":
    asyncio.run(debug_json_structure())
