#!/usr/bin/env python3
"""
특정 기사 본문 수집 테스트
"""

import asyncio
from crawlers.major_news.chosun_politics_crawler import ChosunPoliticsCollector
from rich.console import Console

console = Console()

async def test_single_article():
    """특정 기사 본문 수집 테스트"""
    
    collector = ChosunPoliticsCollector()
    
    # 테스트할 기사 URL
    test_url = "https://www.chosun.com/politics/politics_general/2025/08/19/MX46I5KXANFQZICDOXZAUV3VMU/"
    
    console.print(f"🔍 테스트 URL: {test_url}")
    console.print("=" * 80)
    
    try:
        # HTML 방식으로 본문 추출
        console.print("📖 HTML 방식으로 본문 추출 중...")
        html_content = await collector._extract_content_from_html(test_url)
        
        console.print(f"✅ HTML 본문 길이: {len(html_content)}자")
        console.print("📄 HTML 본문 내용:")
        console.print("-" * 40)
        console.print(html_content[:1000] + "..." if len(html_content) > 1000 else html_content)
        console.print("-" * 40)
        
        # Playwright 방식으로 본문 추출
        console.print("\n🌐 Playwright 방식으로 본문 추출 중...")
        playwright_content = await collector._extract_content_with_playwright(test_url)
        
        console.print(f"✅ Playwright 본문 길이: {len(playwright_content)}자")
        console.print("📄 Playwright 본문 내용:")
        console.print("-" * 40)
        console.print(playwright_content[:1000] + "..." if len(playwright_content) > 1000 else playwright_content)
        console.print("-" * 40)
        
        # 비교
        console.print("\n📊 본문 길이 비교:")
        console.print(f"   HTML: {len(html_content)}자")
        console.print(f"   Playwright: {len(playwright_content)}자")
        
        if len(html_content) > len(playwright_content):
            console.print("✅ HTML 방식이 더 많은 본문을 수집했습니다!")
        elif len(playwright_content) > len(html_content):
            console.print("✅ Playwright 방식이 더 많은 본문을 수집했습니다!")
        else:
            console.print("✅ 두 방식 모두 동일한 길이의 본문을 수집했습니다!")
            
    except Exception as e:
        console.print(f"❌ 오류 발생: {str(e)}")
    finally:
        await collector._cleanup_playwright()

if __name__ == "__main__":
    asyncio.run(test_single_article())
