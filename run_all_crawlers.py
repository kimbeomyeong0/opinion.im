#!/usr/bin/env python3
"""
20개 크롤러 순차 실행 및 결과 레포트 스크립트
"""

import asyncio
import subprocess
import time
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
import json

console = Console()

# 크롤러 목록 (20개)
CRAWLERS = [
    # Major News (17개)
    ("crawlers/major_news/chosun_politics_crawler.py", "조선일보"),
    ("crawlers/major_news/donga_politics_crawler.py", "동아일보"),
    ("crawlers/major_news/joongang_politics_crawler.py", "중앙일보"),
    ("crawlers/major_news/hani_politics_crawler.py", "한겨레"),
    ("crawlers/major_news/hankyung_politics_crawler.py", "한국경제"),
    ("crawlers/major_news/kmib_politics_crawler.py", "국민일보"),
    ("crawlers/major_news/khan_politics_crawler.py", "경향신문"),
    ("crawlers/major_news/kbs_politics_api_collector.py", "KBS"),
    ("crawlers/major_news/news1_politics_crawler.py", "뉴스1"),
    ("crawlers/major_news/segye_politics_crawler.py", "세계일보"),
    ("crawlers/major_news/sbs_politics_crawler.py", "SBS"),
    ("crawlers/major_news/mk_politics_crawler.py", "매일경제"),
    ("crawlers/major_news/yna_politics_crawler.py", "연합뉴스"),
    ("crawlers/major_news/ytn_politics_crawler.py", "YTN"),
    ("crawlers/major_news/sedaily_politics_crawler.py", "서울경제"),
    ("crawlers/major_news/munhwa_politics_crawler.py", "문화일보"),
    ("crawlers/major_news/jtbc_politics_collector.py", "JTBC"),
    
    # Broadcasting (1개)
    ("crawlers/broadcasting/mbc_politics_crawler.py", "MBC"),
    
    # Online News (2개)
    ("crawlers/online_news/pressian_politics_crawler.py", "프레시안"),
    ("crawlers/online_news/ohmynews_politics_crawler.py", "오마이뉴스"),
]

class CrawlerResult:
    def __init__(self, name, path):
        self.name = name
        self.path = path
        self.status = "대기중"
        self.start_time = None
        self.end_time = None
        self.duration = None
        self.articles_collected = 0
        self.error_message = None
        self.exit_code = None

async def run_crawler(crawler_path: str, crawler_name: str) -> CrawlerResult:
    """개별 크롤러 실행"""
    result = CrawlerResult(crawler_name, crawler_path)
    result.start_time = datetime.now()
    
    try:
        console.print(f"🚀 {crawler_name} 크롤러 실행 시작...")
        
        # 크롤러 실행
        process = await asyncio.create_subprocess_exec(
            "python3", crawler_path,
            env={"PYTHONPATH": "."},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        result.exit_code = process.returncode
        
        if result.exit_code == 0:
            result.status = "성공"
            # stdout에서 수집된 기사 수 추출 시도
            output = stdout.decode('utf-8')
            if "수집 결과:" in output:
                # 수집 결과 파싱
                lines = output.split('\n')
                for line in lines:
                    if "총 수집:" in line:
                        try:
                            articles_str = line.split("총 수집:")[1].split("개")[0].strip()
                            result.articles_collected = int(articles_str)
                        except:
                            result.articles_collected = 0
                        break
        else:
            result.status = "실패"
            result.error_message = stderr.decode('utf-8')[:200] + "..." if len(stderr.decode('utf-8')) > 200 else stderr.decode('utf-8')
            
    except Exception as e:
        result.status = "오류"
        result.error_message = str(e)
        result.exit_code = -1
    
    result.end_time = datetime.now()
    result.duration = (result.end_time - result.start_time).total_seconds()
    
    return result

async def run_all_crawlers():
    """모든 크롤러 실행"""
    console.print(Panel.fit("🕷️ 20개 크롤러 순차 실행 시작", style="bold blue"))
    console.print(f"📅 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    console.print("=" * 80)
    
    results = []
    total_start_time = datetime.now()
    
    # 크롤러 순차 실행
    for i, (crawler_path, crawler_name) in enumerate(CRAWLERS, 1):
        console.print(f"\n📰 [{i:2d}/20] {crawler_name} 크롤러 실행 중...")
        
        result = await run_crawler(crawler_path, crawler_name)
        results.append(result)
        
        # 결과 출력
        if result.status == "성공":
            console.print(f"✅ {crawler_name}: {result.articles_collected}개 기사 수집 ({result.duration:.1f}초)")
        else:
            console.print(f"❌ {crawler_name}: {result.status} - {result.error_message}")
        
        # 크롤러 간 간격
        if i < len(CRAWLERS):
            console.print("⏳ 다음 크롤러 준비 중... (3초 대기)")
            await asyncio.sleep(3)
    
    total_end_time = datetime.now()
    total_duration = (total_end_time - total_start_time).total_seconds()
    
    # 결과 레포트 생성
    generate_report(results, total_duration)
    
    return results

def generate_report(results, total_duration):
    """결과 레포트 생성"""
    console.print("\n" + "=" * 80)
    console.print("📊 크롤러 실행 결과 레포트")
    console.print("=" * 80)
    
    # 요약 통계
    successful = sum(1 for r in results if r.status == "성공")
    failed = sum(1 for r in results if r.status == "실패")
    error = sum(1 for r in results if r.status == "오류")
    total_articles = sum(r.articles_collected for r in results if r.status == "성공")
    
    console.print(f"🎯 전체 크롤러: {len(results)}개")
    console.print(f"✅ 성공: {successful}개")
    console.print(f"❌ 실패: {failed}개")
    console.print(f"⚠️ 오류: {error}개")
    console.print(f"📰 총 수집 기사: {total_articles:,}개")
    console.print(f"⏱️ 총 소요 시간: {total_duration:.1f}초")
    
    # 상세 결과 테이블
    table = Table(title="크롤러별 상세 결과")
    table.add_column("순번", style="cyan", no_wrap=True)
    table.add_column("언론사", style="magenta")
    table.add_column("상태", style="bold")
    table.add_column("수집 기사", style="green")
    table.add_column("소요 시간", style="yellow")
    table.add_column("비고", style="red")
    
    for i, result in enumerate(results, 1):
        status_style = {
            "성공": "✅",
            "실패": "❌",
            "오류": "⚠️"
        }.get(result.status, "❓")
        
        articles = f"{result.articles_collected:,}개" if result.articles_collected > 0 else "-"
        duration = f"{result.duration:.1f}초" if result.duration else "-"
        note = result.error_message if result.error_message else "-"
        
        table.add_row(
            str(i),
            result.name,
            f"{status_style} {result.status}",
            articles,
            duration,
            note
        )
    
    console.print(table)
    
    # 성공/실패 요약
    console.print("\n📈 성공한 크롤러:")
    for result in results:
        if result.status == "성공":
            console.print(f"   ✅ {result.name}: {result.articles_collected:,}개 기사")
    
    if failed > 0 or error > 0:
        console.print("\n❌ 실패한 크롤러:")
        for result in results:
            if result.status in ["실패", "오류"]:
                console.print(f"   ❌ {result.name}: {result.error_message}")
    
    # JSON 결과 저장
    report_data = {
        "summary": {
            "total_crawlers": len(results),
            "successful": successful,
            "failed": failed,
            "error": error,
            "total_articles": total_articles,
            "total_duration": total_duration,
            "start_time": total_start_time.isoformat(),
            "end_time": total_end_time.isoformat()
        },
        "results": [
            {
                "name": r.name,
                "path": r.path,
                "status": r.status,
                "articles_collected": r.articles_collected,
                "duration": r.duration,
                "error_message": r.error_message,
                "exit_code": r.exit_code
            }
            for r in results
        ]
    }
    
    with open("crawler_report.json", "w", encoding="utf-8") as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)
    
    console.print(f"\n💾 상세 결과가 'crawler_report.json' 파일에 저장되었습니다.")

if __name__ == "__main__":
    asyncio.run(run_all_crawlers())
