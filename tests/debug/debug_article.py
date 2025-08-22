import asyncio
import aiohttp
from bs4 import BeautifulSoup
from rich.console import Console
from rich.panel import Panel

console = Console()

async def debug_article_page():
    """조선일보 개별 기사 페이지 HTML 구조 분석"""
    
    # 실제 기사 URL (디버그 결과에서 가져온 것)
    article_url = "https://www.chosun.com/politics/politics_general/2025/08/20/HXC43KR5LVH2XAG5XMMSHWXFJY/"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(article_url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }) as response:
                
                if response.status != 200:
                    console.print(f"[red]접근 실패: {response.status}[/red]")
                    return
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                console.print(Panel(f"🔍 기사 페이지 분석: {article_url}", border_style="blue"))
                
                # 1. 제목 찾기
                console.print("\n[cyan]📝 제목 찾기:[/cyan]")
                title_selectors = [
                    'h1', 'h2', 'h3', 'h4', 
                    '.title', '.headline', '.article-title',
                    '.story-headline', '.headline-text',
                    '[data-testid="headline"]',
                    'title'
                ]
                
                for selector in title_selectors:
                    elements = soup.select(selector)
                    if elements:
                        console.print(f"[green]✅ {selector}: {len(elements)}개 발견[/green]")
                        for elem in elements[:2]:
                            text = elem.get_text(strip=True)
                            if text:
                                console.print(f"   - {text[:100]}...")
                    else:
                        console.print(f"[red]❌ {selector}: 없음[/red]")
                
                # 2. 본문 찾기
                console.print("\n[cyan]📄 본문 찾기:[/cyan]")
                content_selectors = [
                    '.content', '.body', '.article-content', '.article-body',
                    '.text', '.story-content', '.article-text',
                    '.content-text', '.story-body',
                    'article', '.main-content'
                ]
                
                for selector in content_selectors:
                    elements = soup.select(selector)
                    if elements:
                        console.print(f"[green]✅ {selector}: {len(elements)}개 발견[/green]")
                        for elem in elements[:2]:
                            text = elem.get_text(strip=True)
                            if text:
                                console.print(f"   - {text[:150]}...")
                    else:
                        console.print(f"[red]❌ {selector}: 없음[/red]")
                
                # 3. 시간 찾기
                console.print("\n[cyan]⏰ 시간 찾기:[/cyan]")
                time_selectors = [
                    '.time', '.date', '.published-time', '.article-time',
                    '.story-time', '.timestamp', '.publish-date',
                    'time', '.upDate', '.story-date'
                ]
                
                for selector in time_selectors:
                    elements = soup.select(selector)
                    if elements:
                        console.print(f"[green]✅ {selector}: {len(elements)}개 발견[/green]")
                        for elem in elements[:3]:
                            text = elem.get_text(strip=True)
                            if text:
                                console.print(f"   - {text}")
                    else:
                        console.print(f"[red]❌ {selector}: 없음[/red]")
                
                # 4. 기자명 찾기
                console.print("\n[cyan]✍️ 기자명 찾기:[/cyan]")
                author_selectors = [
                    '.author', '.reporter', '.byline', '.writer',
                    '.story-author', '.article-author', '.by-line'
                ]
                
                for selector in author_selectors:
                    elements = soup.select(selector)
                    if elements:
                        console.print(f"[green]✅ {selector}: {len(elements)}개 발견[/green]")
                        for elem in elements[:3]:
                            text = elem.get_text(strip=True)
                            if text:
                                console.print(f"   - {text}")
                    else:
                        console.print(f"[red]❌ {selector}: 없음[/red]")
                
                # 5. 모든 텍스트가 있는 요소 찾기 (긴 텍스트)
                console.print("\n[cyan]🔍 긴 텍스트 요소 찾기:[/cyan]")
                all_elements = soup.find_all(['div', 'p', 'span', 'article', 'section'])
                
                long_text_elements = []
                for elem in all_elements:
                    text = elem.get_text(strip=True)
                    if len(text) > 200:  # 200자 이상
                        long_text_elements.append((elem.name, elem.get('class', []), text[:100]))
                
                console.print(f"[green]긴 텍스트 요소 {len(long_text_elements)}개 발견[/green]")
                for i, (tag, classes, text) in enumerate(long_text_elements[:5], 1):
                    console.print(f"{i}. {tag} {classes}: {text}...")
                
                # 6. HTML 구조 저장
                with open('chosun_article_debug.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                console.print(f"\n[green]💾 기사 HTML이 'chosun_article_debug.html'에 저장되었습니다.[/green]")
                
        except Exception as e:
            console.print(f"[red]에러 발생: {str(e)}[/red]")

if __name__ == "__main__":
    asyncio.run(debug_article_page())
