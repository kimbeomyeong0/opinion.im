#!/usr/bin/env python3
"""
크롤러 순차 실행 스크립트 (조선일보부터) - 개선된 버전
"""

import asyncio
import subprocess
import time
from datetime import datetime
from rich.console import Console
from rich.panel import Panel

console = Console()

# 크롤러 목록 (조선일보부터 순서대로)
CRAWLERS = [
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
    ("crawlers/broadcasting/mbc_politics_crawler.py", "MBC"),
    ("crawlers/online_news/pressian_politics_crawler.py", "프레시안"),
    ("crawlers/online_news/ohmynews_politics_crawler.py", "오마이뉴스"),
]

def analyze_crawler_output(output: str) -> dict:
    """크롤러 출력 결과 분석"""
    result = {
        'success': False,
        'articles_count': 0,
        'error_type': None,
        'details': []
    }
    
    lines = output.split('\n')
    
    # 성공 지표들 확인
    success_indicators = [
        "수집 결과:", "총 수집:", "기사 수집 완료", "저장 완료", 
        "크롤링 완료", "수집 완료", "완료", "성공"
    ]
    
    # 실패 지표들 확인
    failure_indicators = [
        "오류 발생", "실패", "에러", "Error", "Exception", 
        "연결 실패", "인증 실패", "권한 없음"
    ]
    
    # 성공 여부 판단
    has_success = any(indicator in output for indicator in success_indicators)
    has_failure = any(indicator in output for indicator in failure_indicators)
    
    # 기사 수 추출
    articles_count = 0
    for line in lines:
        if "총 수집:" in line:
            try:
                articles_str = line.split("총 수집:")[1].split("개")[0].strip()
                articles_count = int(articles_str)
                break
            except:
                pass
        elif "수집된 기사:" in line:
            try:
                articles_str = line.split("수집된 기사:")[1].split("개")[0].strip()
                articles_count = int(articles_str)
                break
            except:
                pass
    
    # 최종 성공 여부 판단
    if has_success and not has_failure and articles_count > 0:
        result['success'] = True
        result['articles_count'] = articles_count
    elif has_success and articles_count > 0:
        result['success'] = True
        result['articles_count'] = articles_count
    elif has_failure:
        result['error_type'] = "명시적 오류"
    else:
        result['error_type'] = "결과 불명확"
    
    # 상세 정보 수집
    for line in lines:
        if any(keyword in line for keyword in ["수집", "저장", "완료", "성공", "오류", "실패"]):
            result['details'].append(line.strip())
    
    return result

async def run_crawler(crawler_path: str, crawler_name: str, index: int):
    """개별 크롤러 실행"""
    start_time = time.time()
    
    console.print(f"\n🚀 [{index:2d}/20] {crawler_name} 크롤러 실행 중...")
    
    try:
        # 크롤러 실행
        process = await asyncio.create_subprocess_exec(
            "python3", crawler_path,
            env={"PYTHONPATH": "."},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        duration = time.time() - start_time
        
        # 출력 결과 분석
        output = stdout.decode('utf-8')
        stderr_output = stderr.decode('utf-8')
        
        # 크롤러 출력 분석
        analysis = analyze_crawler_output(output)
        
        if analysis['success']:
            console.print(f"✅ {crawler_name}: 성공 ({duration:.1f}초)")
            console.print(f"   📰 {analysis['articles_count']}개 기사 수집")
            
            # 상세 정보가 있으면 표시
            if analysis['details']:
                for detail in analysis['details'][:2]:  # 최대 2개만
                    console.print(f"   ℹ️  {detail}")
                    
        else:
            # stderr에 실제 오류가 있는지 확인
            if stderr_output and len(stderr_output.strip()) > 0:
                error_msg = stderr_output[:150] + "..." if len(stderr_output) > 150 else stderr_output
                console.print(f"❌ {crawler_name}: 실패 ({duration:.1f}초)")
                console.print(f"   💬 {error_msg}")
            else:
                # stdout에서 오류 정보 확인
                console.print(f"⚠️  {crawler_name}: 결과 불명확 ({duration:.1f}초)")
                console.print(f"   🔍 {analysis['error_type']}")
                if analysis['details']:
                    for detail in analysis['details'][:2]:
                        console.print(f"   ℹ️  {detail}")
            
    except Exception as e:
        duration = time.time() - start_time
        console.print(f"❌ {crawler_name}: 실행 오류 ({duration:.1f}초) - {str(e)}")

async def run_all_crawlers():
    """모든 크롤러 순차 실행"""
    console.print(Panel.fit("🕷️ 크롤러 순차 실행 시작 (조선일보부터)", style="bold blue"))
    console.print(f"📅 시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    console.print("=" * 80)
    
    total_start_time = time.time()
    
    for i, (crawler_path, crawler_name) in enumerate(CRAWLERS, 1):
        await run_crawler(crawler_path, crawler_name, i)
        
        # 마지막 크롤러가 아니면 대기
        if i < len(CRAWLERS):
            console.print("⏳ 다음 크롤러 준비 중... (3초 대기)")
            await asyncio.sleep(3)
    
    total_duration = time.time() - total_start_time
    
    # 결과 요약
    console.print("\n" + "=" * 80)
    console.print("📊 크롤러 실행 완료 요약")
    console.print("=" * 80)
    console.print(f"🎯 전체 크롤러: {len(CRAWLERS)}개")
    console.print(f"⏱️ 총 소요 시간: {total_duration:.1f}초")
    console.print(f"📅 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    console.print("\n💡 참고: exit code가 아닌 실제 출력 내용으로 성공 여부를 판단합니다.")

if __name__ == "__main__":
    asyncio.run(run_all_crawlers())
