#!/usr/bin/env python3
import requests
from bs4 import BeautifulSoup

# 간단한 프레시안 기사 분석
url = "https://www.pressian.com/pages/articles/2025082109082826885"

try:
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    response = requests.get(url, headers=headers, timeout=10)
    
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        
        print("=== 프레시안 기사 구조 분석 ===\n")
        
        # 모든 h1, h2 태그 찾기
        print("1. 모든 h1 태그:")
        h1_tags = soup.find_all('h1')
        for i, h1 in enumerate(h1_tags):
            print(f"  h1[{i}]: {h1.get_text(strip=True)[:100]}")
        
        print("\n2. 모든 h2 태그:")
        h2_tags = soup.find_all('h2')
        for i, h2 in enumerate(h2_tags):
            print(f"  h2[{i}]: {h2.get_text(strip=True)[:100]}")
        
        # class나 id에 title이 포함된 요소들
        print("\n3. title이 포함된 클래스/ID:")
        title_elements = soup.find_all(attrs={'class': lambda x: x and any('title' in cls.lower() for cls in x)})
        for i, elem in enumerate(title_elements[:5]):
            print(f"  title[{i}] ({elem.name}): {elem.get_text(strip=True)[:100]}")
        
        # 페이지 제목 (title 태그)
        page_title = soup.find('title')
        if page_title:
            print(f"\n4. <title> 태그: {page_title.get_text(strip=True)}")
        
        # 메타데이터에서 제목 찾기
        meta_title = soup.find('meta', property='og:title')
        if meta_title:
            print(f"\n5. og:title: {meta_title.get('content')}")
            
    else:
        print(f"HTTP 오류: {response.status_code}")
        
except Exception as e:
    print(f"오류: {e}")
