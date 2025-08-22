import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def debug_donga_article():
    url = "https://www.donga.com/news/Politics/article/all/20250821/132224107/2"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                print("=== 동아일보 기사 페이지 HTML 구조 디버깅 ===")
                
                # title 태그 확인
                title_tag = soup.find('title')
                if title_tag:
                    print(f"<title> 태그: {title_tag.get_text()}")
                
                # og:title 메타 태그 확인
                og_title = soup.find('meta', property='og:title')
                if og_title:
                    print(f"og:title: {og_title.get('content')}")
                
                # h1, h2, h3 태그들 확인
                for i, h_tag in enumerate(soup.find_all(['h1', 'h2', 'h3'])[:5]):
                    print(f"<{h_tag.name}> 태그 {i+1}: {h_tag.get_text(strip=True)}")
                
                # article_title 클래스 확인
                article_title = soup.select('.article_title')
                print(f"\n.article_title 클래스 수: {len(article_title)}")
                
                # article_body 클래스 확인
                article_body = soup.select('.article_body')
                print(f".article_body 클래스 수: {len(article_body)}")
                
                # article_content 클래스 확인
                article_content = soup.select('.article_content')
                print(f".article_content 클래스 수: {len(article_content)}")
                
                # content 클래스 확인
                content = soup.select('.content')
                print(f".content 클래스 수: {len(content)}")
                
                # article_txt 클래스 확인
                article_txt = soup.select('.article_txt')
                print(f".article_txt 클래스 수: {len(article_txt)}")
                
                # 실제 기사 내용이 있는 div 찾기
                print("\n=== 기사 내용이 있을 것 같은 div들 ===")
                for div in soup.find_all('div', class_=True)[:10]:
                    class_names = div.get('class', [])
                    if any('article' in cls.lower() or 'content' in cls.lower() or 'body' in cls.lower() for cls in class_names):
                        print(f"클래스: {class_names}, 텍스트 길이: {len(div.get_text(strip=True))}")

if __name__ == "__main__":
    asyncio.run(debug_donga_article())
