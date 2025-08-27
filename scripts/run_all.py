#!/usr/bin/env python3
"""
모든 크롤러 실행 스크립트
major_news, online_news, broadcasting 디렉토리의 모든 크롤러를 실행
"""

import os
import sys
import importlib
import time
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.logger import get_logger
from common.config import config

logger = get_logger('run_all')

class CrawlerRunner:
    """크롤러 실행 관리자"""
    
    def __init__(self):
        self.logger = logger
        self.crawlers = {}
        self.results = {}
        
    def discover_crawlers(self) -> Dict[str, List[str]]:
        """크롤러 디렉토리에서 크롤러 파일들을 발견"""
        crawler_dirs = ['major_news', 'online_news', 'broadcasting']
        discovered = {}
        
        for dir_name in crawler_dirs:
            dir_path = os.path.join('crawlers', dir_name)
            if os.path.exists(dir_path):
                crawler_files = []
                for file in os.listdir(dir_path):
                    if file.endswith('_crawler.py') or file.endswith('_collector.py'):
                        crawler_name = file.replace('_crawler.py', '').replace('_collector.py', '')
                        crawler_files.append(crawler_name)
                
                if crawler_files:
                    discovered[dir_name] = crawler_files
        
        return discovered
    
    def load_crawler(self, source_type: str, crawler_name: str) -> Any:
        """크롤러 모듈 로드"""
        try:
            module_path = f"crawlers.{source_type}.{crawler_name}_crawler"
            module = importlib.import_module(module_path)
            
            # 크롤러 클래스 찾기 (일반적으로 파일명과 동일한 클래스명 사용)
            crawler_class_name = f"{crawler_name.capitalize()}PoliticsCrawler"
            if hasattr(module, crawler_class_name):
                return getattr(module, crawler_class_name)
            
            # 다른 가능한 클래스명들 시도
            for attr_name in dir(module):
                if attr_name.endswith('Crawler') or attr_name.endswith('Collector'):
                    return getattr(module, attr_name)
            
            self.logger.warning(f"크롤러 클래스를 찾을 수 없음: {module_path}")
            return None
            
        except ImportError as e:
            self.logger.error(f"크롤러 모듈 로드 실패: {source_type}.{crawler_name} - {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"크롤러 로드 중 오류: {source_type}.{crawler_name} - {str(e)}")
            return None
    
    def run_crawler(self, source_type: str, crawler_name: str) -> Dict[str, Any]:
        """개별 크롤러 실행"""
        start_time = time.time()
        result = {
            'source_type': source_type,
            'crawler_name': crawler_name,
            'success': False,
            'article_count': 0,
            'saved_count': 0,
            'error': None,
            'execution_time': 0
        }
        
        try:
            self.logger.info(f"크롤러 시작: {source_type}.{crawler_name}")
            
            # 크롤러 클래스 로드
            crawler_class = self.load_crawler(source_type, crawler_name)
            if not crawler_class:
                result['error'] = "크롤러 클래스를 찾을 수 없음"
                return result
            
            # 크롤러 인스턴스 생성 및 실행
            crawler_instance = crawler_class()
            
            # run 메서드가 있는지 확인
            if hasattr(crawler_instance, 'run'):
                # 기존 run 메서드 실행
                crawler_result = crawler_instance.run()
                
                # 결과 파싱 (기존 형식에 맞춤)
                if isinstance(crawler_result, dict):
                    result['article_count'] = crawler_result.get('article_count', 0)
                    result['saved_count'] = crawler_result.get('saved_count', 0)
                elif isinstance(crawler_result, (list, tuple)):
                    result['article_count'] = len(crawler_result)
                    result['saved_count'] = len(crawler_result)
                else:
                    result['article_count'] = 1 if crawler_result else 0
                    result['saved_count'] = 1 if crawler_result else 0
                
                result['success'] = True
                
            elif hasattr(crawler_instance, 'crawl'):
                # crawl 메서드가 있는 경우
                crawler_result = crawler_instance.crawl()
                result['article_count'] = len(crawler_result) if isinstance(crawler_result, list) else 1
                result['saved_count'] = result['article_count']
                result['success'] = True
                
            else:
                result['error'] = "실행 가능한 메서드가 없음 (run 또는 crawl)"
            
        except Exception as e:
            result['error'] = str(e)
            self.logger.error(f"크롤러 실행 중 오류: {source_type}.{crawler_name} - {str(e)}")
        
        finally:
            result['execution_time'] = time.time() - start_time
            self.logger.info(f"크롤러 완료: {source_type}.{crawler_name} - "
                           f"수집: {result['article_count']}개, 저장: {result['saved_count']}개, "
                           f"소요시간: {result['execution_time']:.2f}초")
        
        return result
    
    def run_all_crawlers(self, max_workers: int = None) -> Dict[str, Any]:
        """모든 크롤러 실행"""
        if max_workers is None:
            max_workers = config.MAX_WORKERS
        
        # 크롤러 발견
        discovered_crawlers = self.discover_crawlers()
        if not discovered_crawlers:
            self.logger.error("실행 가능한 크롤러를 찾을 수 없습니다.")
            return {}
        
        self.logger.info(f"발견된 크롤러: {discovered_crawlers}")
        
        # 실행할 크롤러 목록 생성
        crawler_tasks = []
        for source_type, crawler_names in discovered_crawlers.items():
            for crawler_name in crawler_names:
                crawler_tasks.append((source_type, crawler_name))
        
        self.logger.info(f"총 {len(crawler_tasks)}개 크롤러 실행 예정")
        
        # 병렬 실행
        results = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 작업 제출
            future_to_crawler = {
                executor.submit(self.run_crawler, source_type, crawler_name): (source_type, crawler_name)
                for source_type, crawler_name in crawler_tasks
            }
            
            # 결과 수집
            for future in as_completed(future_to_crawler):
                source_type, crawler_name = future_to_crawler[future]
                try:
                    result = future.result()
                    results[f"{source_type}.{crawler_name}"] = result
                except Exception as e:
                    self.logger.error(f"크롤러 실행 실패: {source_type}.{crawler_name} - {str(e)}")
                    results[f"{source_type}.{crawler_name}"] = {
                        'source_type': source_type,
                        'crawler_name': crawler_name,
                        'success': False,
                        'article_count': 0,
                        'saved_count': 0,
                        'error': str(e),
                        'execution_time': 0
                    }
        
        return results
    
    def print_summary(self, results: Dict[str, Any]):
        """실행 결과 요약 출력"""
        if not results:
            self.logger.info("실행된 크롤러가 없습니다.")
            return
        
        total_crawlers = len(results)
        successful_crawlers = sum(1 for r in results.values() if r['success'])
        total_articles = sum(r['article_count'] for r in results.values())
        total_saved = sum(r['saved_count'] for r in results.values())
        total_time = sum(r['execution_time'] for r in results.values())
        
        self.logger.info("=" * 60)
        self.logger.info("크롤러 실행 결과 요약")
        self.logger.info("=" * 60)
        self.logger.info(f"총 크롤러 수: {total_crawlers}")
        self.logger.info(f"성공한 크롤러 수: {successful_crawlers}")
        self.logger.info(f"실패한 크롤러 수: {total_crawlers - successful_crawlers}")
        self.logger.info(f"총 수집 기사 수: {total_articles}")
        self.logger.info(f"총 저장 기사 수: {total_saved}")
        self.logger.info(f"총 소요 시간: {total_time:.2f}초")
        self.logger.info("=" * 60)
        
        # 실패한 크롤러 목록
        failed_crawlers = [name for name, result in results.items() if not result['success']]
        if failed_crawlers:
            self.logger.warning(f"실패한 크롤러: {', '.join(failed_crawlers)}")

def main():
    """메인 함수"""
    logger.info("모든 크롤러 실행 시작")
    
    # 설정 검증
    if not config.validate_config():
        logger.warning("설정 검증 실패. 계속 진행합니다.")
    
    # 크롤러 실행
    runner = CrawlerRunner()
    results = runner.run_all_crawlers()
    
    # 결과 요약
    runner.print_summary(results)
    
    logger.info("모든 크롤러 실행 완료")

if __name__ == "__main__":
    main()
