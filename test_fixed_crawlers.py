#!/usr/bin/env python3
"""
수정된 크롤러들 테스트 스크립트
"""

import asyncio
import subprocess
import time
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# 수정된 크롤러 목록 (5개만 테스트)
TEST_CRAWLERS = [
    ("crawlers/major_news/donga_politics_crawler.py", "동아일보"),
    ("crawlers/major_news/joongang_politics_crawler.py", "중앙일보"),
    ("crawlers/major_news/hani_politics_crawler.py", "한겨레"),
    ("crawlers/major_news/kmib_politics_crawler.py", "국민일보"),
    ("crawlers/major_news/khan_politics_crawler.py", "경향신문"),
]

async def run_crawler(crawler_path: str, crawler_name: str):
    """개별 크롤러 실행"""
    console.print(f"🚀 {crawler_name} 크롤러 실행 시작...")
    
    try:
        process = await asyncio.create_subprocess_exec(
            "python3", crawler_path,
            env={"PYTHONPATH": "."},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            console.print(f"✅ {crawler_name}: 성공")
            # stdout에서 수집된 기사 수 추출
            output = stdout.decode('utf-8')
            if "수집 결과:" in output:
                lines = output.split('\n')
                for line in lines:
                    if "총 수집:" in line:
                        try:
                            articles_str = line.split("총 수집:")[1].split("개")[0].strip()
                            articles_count = int(articles_str)
                            console.print(f"   📰 {articles_count}개 기사 수집")
                        except:
                            console.print(f"   📰 기사 수집 정보 없음")
                        break
        else:
            console.print(f"❌ {crawler_name}: 실패")
            error_msg = stderr.decode('utf-8')[:200] + "..." if len(stderr.decode('utf-8')) > 200 else stderr.decode('utf-8')
            console.print(f"   💬 {error_msg}")
            
    except Exception as e:
        console.print(f"❌ {crawler_name}: 오류 - {str(e)}")

async def test_fixed_crawlers():
    """수정된 크롤러들 테스트"""
    console.print(Panel.fit("🔧 수정된 크롤러들 테스트 시작", style="bold green"))
    console.print(f"📅 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    console.print("=" * 60)
    
    for i, (crawler_path, crawler_name) in enumerate(TEST_CRAWLERS, 1):
        console.print(f"\n📰 [{i:2d}/5] {crawler_name} 크롤러 테스트 중...")
        
        await run_crawler(crawler_path, crawler_name)
        
        # 크롤러 간 간격
        if i < len(TEST_CRAWLERS):
            console.print("⏳ 다음 크롤러 준비 중... (5초 대기)")
            await asyncio.sleep(5)
    
    console.print("\n" + "=" * 60)
    console.print("🎯 테스트 완료!")

if __name__ == "__main__":
    asyncio.run(test_fixed_crawlers())

