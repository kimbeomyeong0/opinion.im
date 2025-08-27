#!/usr/bin/env python3
"""
HTML 구조 디버깅 스크립트
"""

import asyncio
import httpx
import re
from bs4 import BeautifulSoup
from rich.console import Console

console = Console()

async def debug_html_structure():
    """HTML 구조 디버깅"""
    
    url = "https://www.chosun.com/politics/politics_general/2025/08/19/MX46I5KXANFQZICDOXZAUV3VMU/"
    
    console.print(f"🔍 URL: {url}")
    console.print("=" * 80)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            html = response.text
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. HTML 전체 길이
        console.print(f"📊 HTML 전체 길이: {len(html)}자")
        
        # 2. 모든 태그 분석
        console.print("\n📋 2. 모든 태그 분석:")
        all_tags = soup.find_all()
        tag_counts = {}
        for tag in all_tags:
            tag_name = tag.name
            if tag_name not in tag_counts:
                tag_counts[tag_name] = 0
            tag_counts[tag_name] += 1
        
        for tag_name, count in sorted(tag_counts.items()):
            console.print(f"   - {tag_name}: {count}개")
        
        # 3. script 태그 내용 분석
        console.print("\n📋 3. Script 태그 분석:")
        scripts = soup.find_all('script')
        console.print(f"총 script 태그: {len(scripts)}개")
        
        for i, script in enumerate(scripts):
            if script.string:
                script_content = script.string
                console.print(f"   - script[{i}]: {len(script_content)}자")
                
                # 본문 관련 키워드 검색
                keywords = ['content', 'body', 'article', 'text', '본문', '기사']
                for keyword in keywords:
                    if keyword in script_content:
                        console.print(f"     ✅ '{keyword}' 키워드 발견")
                
                # JSON 데이터 검색
                if 'content_elements' in script_content or 'articleBody' in script_content:
                    console.print(f"     🔍 본문 관련 데이터 발견!")
                    
                    # JSON 부분 추출 시도
                    json_match = re.search(r'\{.*"content_elements".*\}', script_content, re.DOTALL)
                    if json_match:
                        console.print(f"     📄 JSON 데이터 길이: {len(json_match.group())}자")
        
        # 4. div 태그 중 텍스트가 있는 것들
        console.print("\n📋 4. 텍스트가 있는 div 태그들:")
        text_divs = []
        for div in soup.find_all('div'):
            text = div.get_text(strip=True)
            if len(text) > 50:  # 50자 이상
                classes = ' '.join(div.get('class', []))
                text_divs.append((classes, len(text), text[:150]))
        
        text_divs.sort(key=lambda x: x[1], reverse=True)
        
        for i, (classes, length, text) in enumerate(text_divs[:10]):
            console.print(f"   {i+1}. div.{classes}: {length}자")
            console.print(f"      내용: {text}...")
        
        # 5. 특정 클래스나 ID를 가진 요소들
        console.print("\n📋 5. 특정 클래스/ID 요소들:")
        interesting_selectors = [
            '[class*="article"]',
            '[class*="content"]',
            '[class*="body"]',
            '[class*="text"]',
            '[id*="article"]',
            '[id*="content"]'
        ]
        
        for selector in interesting_selectors:
            elements = soup.select(selector)
            if elements:
                console.print(f"   ✅ {selector}: {len(elements)}개")
                for elem in elements[:3]:  # 처음 3개만
                    text = elem.get_text(strip=True)
                    console.print(f"      - {elem.name}.{'.'.join(elem.get('class', []))}: {len(text)}자")
            else:
                console.print(f"   ❌ {selector}: 없음")
        
        # 6. HTML 전체에서 본문 관련 텍스트 검색
        console.print("\n📋 6. 본문 관련 텍스트 검색:")
        full_text = soup.get_text()
        
        # 본문으로 보이는 긴 텍스트 찾기
        sentences = re.split(r'[.!?]', full_text)
        long_sentences = [s.strip() for s in sentences if len(s.strip()) > 100]
        
        console.print(f"100자 이상 문장: {len(long_sentences)}개")
        for i, sentence in enumerate(long_sentences[:5]):
            console.print(f"   {i+1}. {sentence[:200]}...")
        
    except Exception as e:
        console.print(f"❌ 오류 발생: {str(e)}")

if __name__ == "__main__":
    asyncio.run(debug_html_structure())
