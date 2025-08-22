import asyncio
import aiohttp
from bs4 import BeautifulSoup
from rich.console import Console
from rich.panel import Panel
import json

console = Console()

async def debug_chosun_politics():
    """조선일보 정치 페이지 HTML 구조 분석"""
    
    url = "https://www.chosun.com/politics/"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }) as response:
                
                if response.status != 200:
                    console.print(f"[red]접근 실패: {response.status}[/red]")
                    return
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                console.print(Panel("🔍 조선일보 정치 페이지 HTML 구조 분석", border_style="blue"))
                
                # 1. 모든 링크 찾기
                all_links = soup.find_all('a', href=True)
                politics_links = [link for link in all_links if '/politics/' in link.get('href', '')]
                
                console.print(f"[green]총 링크 수: {len(all_links)}[/green]")
                console.print(f"[green]정치 관련 링크 수: {len(politics_links)}[/green]")
                
                # 2. 정치 링크 상세 분석
                console.print("\n[cyan]📰 정치 링크 상세 분석:[/cyan]")
                for i, link in enumerate(politics_links[:10], 1):  # 상위 10개만
                    href = link.get('href')
                    text = link.get_text(strip=True)
                    parent_tag = link.parent.name if link.parent else "None"
                    parent_class = link.parent.get('class', []) if link.parent else []
                    
                    console.print(f"{i}. {text[:50]}...")
                    console.print(f"   URL: {href}")
                    console.print(f"   부모: {parent_tag} {parent_class}")
                    console.print()
                
                # 3. 제목 요소 찾기
                console.print("\n[cyan]📝 제목 요소 찾기:[/cyan]")
                title_selectors = ['h1', 'h2', 'h3', 'h4', '.title', '.headline', '.article-title']
                
                for selector in title_selectors:
                    elements = soup.select(selector)
                    if elements:
                        console.print(f"[green]✅ {selector}: {len(elements)}개 발견[/green]")
                        for elem in elements[:3]:  # 상위 3개만
                            text = elem.get_text(strip=True)
                            if text:
                                console.print(f"   - {text[:50]}...")
                    else:
                        console.print(f"[red]❌ {selector}: 없음[/red]")
                
                # 4. 본문 요소 찾기
                console.print("\n[cyan]📄 본문 요소 찾기:[/cyan]")
                content_selectors = ['.content', '.body', '.article-content', '.article-body', '.text', 'article']
                
                for selector in content_selectors:
                    elements = soup.select(selector)
                    if elements:
                        console.print(f"[green]✅ {selector}: {len(elements)}개 발견[/green]")
                        for elem in elements[:2]:  # 상위 2개만
                            text = elem.get_text(strip=True)
                            if text:
                                console.print(f"   - {text[:100]}...")
                    else:
                        console.print(f"[red]❌ {selector}: 없음[/red]")
                
                # 5. 시간 요소 찾기
                console.print("\n[cyan]⏰ 시간 요소 찾기:[/cyan]")
                time_selectors = ['.time', '.date', '.published-time', '.article-time', 'time']
                
                for selector in time_selectors:
                    elements = soup.select(selector)
                    if elements:
                        console.print(f"[green]✅ {selector}: {len(elements)}개 발견[/green]")
                        for elem in elements[:3]:  # 상위 3개만
                            text = elem.get_text(strip=True)
                            if text:
                                console.print(f"   - {text}")
                    else:
                        console.print(f"[red]❌ {selector}: 없음[/red]")
                
                # 6. 실제 기사 URL 패턴 분석
                console.print("\n[cyan]🔗 기사 URL 패턴 분석:[/cyan]")
                article_urls = []
                for link in politics_links:
                    href = link.get('href')
                    if href and len(href) > 20:  # 실제 기사 링크는 길이가 김
                        article_urls.append(href)
                
                # URL 패턴 그룹화
                url_patterns = {}
                for url in article_urls[:20]:  # 상위 20개만
                    if url.startswith('/'):
                        url = url
                    
                    # 패턴 추출
                    if '/politics/' in url:
                        if '/article/' in url:
                            pattern = '/politics/article/'
                        elif '/north_korea/' in url:
                            pattern = '/politics/north_korea/'
                        elif '/politics_general/' in url:
                            pattern = '/politics/politics_general/'
                        else:
                            pattern = '/politics/'
                    else:
                        pattern = 'other'
                    
                    if pattern not in url_patterns:
                        url_patterns[pattern] = []
                    url_patterns[pattern].append(url)
                
                for pattern, urls in url_patterns.items():
                    console.print(f"[yellow]{pattern}: {len(urls)}개[/yellow]")
                    for url in urls[:3]:  # 상위 3개만
                        console.print(f"   - {url}")
                
                # 7. HTML 구조 저장 (디버깅용)
                with open('chosun_politics_debug.html', 'w', encoding='utf-8') as f:
                    f.write(html)
                console.print(f"\n[green]💾 HTML 구조가 'chosun_politics_debug.html'에 저장되었습니다.[/green]")
                
        except Exception as e:
            console.print(f"[red]에러 발생: {str(e)}[/red]")

if __name__ == "__main__":
    asyncio.run(debug_chosun_politics())
