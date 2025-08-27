#!/usr/bin/env python3
"""
기본 테스트 코드
크롤러의 기본 기능과 공통 모듈을 테스트
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common.logger import get_logger
from common.config import config
from common.parser_utils import ParserUtils
from common.supabase_manager import SupabaseManager

class TestBasicFunctionality(unittest.TestCase):
    """기본 기능 테스트"""
    
    def setUp(self):
        """테스트 설정"""
        self.logger = get_logger('test_basic')
    
    def test_config_loading(self):
        """설정 로딩 테스트"""
        self.assertIsNotNone(config)
        self.assertTrue(hasattr(config, 'NEWS_SOURCES'))
        self.assertTrue(hasattr(config, 'SUPABASE_URL'))
    
    def test_parser_utils(self):
        """파서 유틸리티 테스트"""
        # 날짜 파싱 테스트
        date_str = "2025년 8월 22일"
        parsed_date = ParserUtils.parse_date(date_str)
        self.assertEqual(parsed_date, "2025-08-22")
        
        # 제목 정리 테스트
        title = "[속보]  대통령,  '정치 개혁'  강조"
        cleaned_title = ParserUtils.clean_title(title)
        self.assertEqual(cleaned_title, "속보 대통령, '정치 개혁' 강조")
        
        # 본문 정리 테스트
        content = "정치 뉴스입니다.\n\n[광고] 광고 내용\n\n김철수 기자"
        cleaned_content = ParserUtils.clean_content(content)
        self.assertNotIn("광고", cleaned_content)
        self.assertNotIn("김철수 기자", cleaned_content)
    
    def test_logger(self):
        """로거 테스트"""
        logger = get_logger('test')
        self.assertIsNotNone(logger)
        self.assertEqual(logger.level, 20)  # INFO level
    
    @patch('common.supabase_manager.create_client')
    def test_supabase_manager(self, mock_create_client):
        """Supabase 매니저 테스트 (모킹)"""
        # 모킹 설정
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        
        # 환경변수 설정
        with patch.dict(os.environ, {
            'SUPABASE_URL': 'https://test.supabase.co',
            'SUPABASE_KEY': 'test_key'
        }):
            manager = SupabaseManager()
            self.assertIsNotNone(manager)
            self.assertTrue(manager.is_connected())

class TestCrawlerDiscovery(unittest.TestCase):
    """크롤러 발견 테스트"""
    
    def test_crawler_directories_exist(self):
        """크롤러 디렉토리 존재 확인"""
        crawler_dirs = ['crawlers/major_news', 'crawlers/online_news', 'crawlers/broadcasting']
        
        for dir_path in crawler_dirs:
            with self.subTest(dir_path=dir_path):
                self.assertTrue(os.path.exists(dir_path), f"디렉토리가 존재하지 않음: {dir_path}")
    
    def test_crawler_files_exist(self):
        """크롤러 파일 존재 확인"""
        major_news_dir = 'crawlers/major_news'
        if os.path.exists(major_news_dir):
            crawler_files = [f for f in os.listdir(major_news_dir) if f.endswith('_crawler.py')]
            self.assertGreater(len(crawler_files), 0, "major_news에 크롤러 파일이 없음")
            
            # 조선일보 크롤러 확인
            chosun_crawler = 'chosun_politics_crawler.py'
            self.assertTrue(
                chosun_crawler in crawler_files,
                f"조선일보 크롤러가 없음: {chosun_crawler}"
            )

class TestCommonModules(unittest.TestCase):
    """공통 모듈 테스트"""
    
    def test_imports(self):
        """모듈 import 테스트"""
        try:
            from common.logger import get_logger
            from common.config import config
            from common.parser_utils import ParserUtils
            from common.supabase_manager import SupabaseManager
            self.assertTrue(True, "모든 공통 모듈을 성공적으로 import함")
        except ImportError as e:
            self.fail(f"모듈 import 실패: {e}")
    
    def test_parser_utils_methods(self):
        """파서 유틸리티 메서드 테스트"""
        # 모든 필요한 메서드가 존재하는지 확인
        required_methods = [
            'parse_date', 'clean_title', 'clean_content',
            'extract_text_from_html', 'extract_author'
        ]
        
        for method_name in required_methods:
            with self.subTest(method_name=method_name):
                self.assertTrue(
                    hasattr(ParserUtils, method_name),
                    f"메서드가 없음: {method_name}"
                )

def run_basic_tests():
    """기본 테스트 실행"""
    print("기본 기능 테스트 시작...")
    
    # 테스트 스위트 생성
    test_suite = unittest.TestSuite()
    
    # 테스트 클래스들 추가
    test_suite.addTest(unittest.makeSuite(TestBasicFunctionality))
    test_suite.addTest(unittest.makeSuite(TestCrawlerDiscovery))
    test_suite.addTest(unittest.makeSuite(TestCommonModules))
    
    # 테스트 실행
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # 결과 요약
    print(f"\n테스트 결과: {result.testsRun}개 실행, {len(result.failures)}개 실패, {len(result.errors)}개 오류")
    
    if result.failures:
        print("\n실패한 테스트:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback}")
    
    if result.errors:
        print("\n오류가 발생한 테스트:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback}")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_basic_tests()
    sys.exit(0 if success else 1)
