import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def debug_donga_structure():
    url = "https://www.donga.com/news/Politics"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                print("=== 동아일보 HTML 구조 디버깅 ===")
                
                # 최신기사 섹션 확인
                sub_news = soup.select('.sub_news_sec')
                print(f"최신기사 섹션 수: {len(sub_news)}")
                
                if sub_news:
                    print("첫 번째 최신기사 섹션 내용:")
                    print(sub_news[0].prettify()[:1000])
                
                # 톱기사 섹션 확인
                head_news = soup.select('.head_news_sec')
                print(f"\n톱기사 섹션 수: {len(head_news)}")
                
                if head_news:
                    print("첫 번째 톱기사 섹션 내용:")
                    print(head_news[0].prettify()[:1000])
                
                # news_card 확인
                news_cards = soup.select('.news_card')
                print(f"\n총 news_card 수: {len(news_cards)}")
                
                if news_cards:
                    print("첫 번째 news_card 내용:")
                    print(news_cards[0].prettify()[:500])
                
                # tit a 확인
                tit_links = soup.select('.tit a')
                print(f"\n총 .tit a 수: {len(tit_links)}")
                
                if tit_links:
                    print("첫 번째 .tit a 내용:")
                    print(tit_links[0].prettify())
                    print(f"href: {tit_links[0].get('href')}")

if __name__ == "__main__":
    asyncio.run(debug_donga_structure())
