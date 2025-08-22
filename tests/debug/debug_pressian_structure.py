#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
프레시안 기사 페이지 HTML 구조 분석
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def analyze_pressian_article():
    """프레시안 기사 페이지 구조를 분석합니다."""
    
    # 테스트용 기사 URL (실제 기사 링크)
    test_url = "https://www.pressian.com/pages/articles/2025082109082826885"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(test_url) as response:
            if response.status == 200:
                html_content = await response.text()
                
                soup = BeautifulSoup(html_content, 'html.parser')
                
                print("=== 프레시안 기사 페이지 구조 분석 ===\n")
                
                # 1. 제목 찾기
                print("1. 제목 선택자들:")
                title_selectors = [
                    'h1.title', 'h2.title', 'h3.title', 'p.title', '.title',
                    'h1', 'h2', 'h3', '.article-title', '.headline'
                ]
                
                for selector in title_selectors:
                    elem = soup.select_one(selector)
                    if elem:
                        print(f"  {selector}: {elem.get_text(strip=True)[:100]}")
                
                print("\n2. 본문 선택자들:")
                content_selectors = [
                    'div.article-content', 'div.content', 'div.body', 'div.article-body',
                    'div.text', 'article', 'div.arl_022', '.article-text', '.post-content'
                ]
                
                for selector in content_selectors:
                    elem = soup.select_one(selector)
                    if elem:
                        text = elem.get_text(strip=True)
                        print(f"  {selector}: {len(text)}자 - {text[:100]}...")
                
                print("\n3. 날짜 선택자들:")
                date_selectors = [
                    'p.date', '.date', '.publish-date', '.article-date', 'time', '[datetime]'
                ]
                
                for selector in date_selectors:
                    elem = soup.select_one(selector)
                    if elem:
                        print(f"  {selector}: {elem.get_text(strip=True)}")
                
                print("\n4. 전체 HTML에서 '기자' 키워드 검색:")
                full_text = soup.get_text()
                lines = full_text.split('\n')
                for i, line in enumerate(lines):
                    if '기자' in line and len(line.strip()) < 100:
                        print(f"  라인 {i+1}: {line.strip()}")
                
                print("\n5. 주요 div 클래스들:")
                main_divs = soup.find_all('div', class_=True)
                classes = set()
                for div in main_divs:
                    if div.get('class'):
                        classes.update(div.get('class'))
                
                for cls in sorted(list(classes))[:20]:  # 처음 20개만
                    print(f"  {cls}")
                
            else:
                print(f"페이지 로드 실패: {response.status}")

if __name__ == "__main__":
    asyncio.run(analyze_pressian_article())
