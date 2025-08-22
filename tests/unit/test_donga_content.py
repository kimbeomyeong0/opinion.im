import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def test_donga_content():
    url = "https://www.donga.com/news/Politics/article/all/20250820/132221972/1"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                print("=== 동아일보 기사 본문 추출 테스트 ===")
                
                # 1. news_view 섹션 찾기
                news_view = soup.select_one('section.news_view')
                if news_view:
                    print(f"✅ news_view 섹션 발견: {len(news_view.get_text())}자")
                    
                    # 광고 요소 제거
                    for unwanted in news_view.select('.view_ad06, .view_m_adA, .view_m_adB, .view_m_adK, .a1, script, .ad'):
                        unwanted.decompose()
                    
                    # 텍스트 추출
                    content = news_view.get_text(separator='\n', strip=True)
                    content = '\n'.join(line.strip() for line in content.split('\n') if line.strip())
                    
                    print(f"\n📰 추출된 본문 (처음 500자):")
                    print(content[:500])
                    print(f"\n📊 전체 본문 길이: {len(content)}자")
                    
                else:
                    print("❌ news_view 섹션을 찾을 수 없습니다")
                
                # 2. 기존 메타 태그 확인
                og_desc = soup.find('meta', property='og:description')
                if og_desc:
                    print(f"\n🔍 og:description: {og_desc.get('content', '')[:200]}...")
                
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc:
                    print(f"🔍 meta description: {meta_desc.get('content', '')[:200]}...")

if __name__ == "__main__":
    asyncio.run(test_donga_content())
