#!/usr/bin/env python3
"""
공통 로깅 유틸리티
크롤러 실행 시 일관된 로그 형식과 레벨을 제공
"""

import logging
import os
from datetime import datetime
from typing import Optional

class Logger:
    """통합 로깅 관리자"""
    
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._setup_logging()
            self._initialized = True
    
    def _setup_logging(self):
        """로깅 설정 초기화"""
        # logs 디렉토리 생성
        os.makedirs('logs', exist_ok=True)
        
        # 로그 파일명 설정 (날짜별)
        today = datetime.now().strftime('%Y-%m-%d')
        log_filename = f'logs/crawler_{today}.log'
        
        # 로거 설정
        self.logger = logging.getLogger('opinion_crawler')
        self.logger.setLevel(logging.INFO)
        
        # 기존 핸들러 제거 (중복 방지)
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # 파일 핸들러
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # 포맷터
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 핸들러 추가
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def get_logger(self, name: str = None) -> logging.Logger:
        """
        로거 인스턴스 반환
        
        Args:
            name: 로거 이름 (기본값: None)
        
        Returns:
            로거 인스턴스
        """
        if name:
            return logging.getLogger(f'opinion_crawler.{name}')
        return self.logger
    
    def info(self, message: str, logger_name: str = None):
        """정보 로그"""
        logger = self.get_logger(logger_name)
        logger.info(message)
    
    def warning(self, message: str, logger_name: str = None):
        """경고 로그"""
        logger = self.get_logger(logger_name)
        logger.warning(message)
    
    def error(self, message: str, logger_name: str = None):
        """에러 로그"""
        logger = self.get_logger(logger_name)
        logger.error(message)
    
    def debug(self, message: str, logger_name: str = None):
        """디버그 로그"""
        logger = self.get_logger(logger_name)
        logger.debug(message)
    
    def log_crawler_start(self, crawler_name: str, target_url: str = None):
        """크롤러 시작 로그"""
        message = f"크롤러 시작: {crawler_name}"
        if target_url:
            message += f" - URL: {target_url}"
        self.info(message, crawler_name)
    
    def log_crawler_end(self, crawler_name: str, article_count: int, saved_count: int):
        """크롤러 완료 로그"""
        message = f"크롤러 완료: {crawler_name} - 수집: {article_count}개, 저장: {saved_count}개"
        self.info(message, crawler_name)
    
    def log_article_parsed(self, crawler_name: str, title: str, url: str):
        """기사 파싱 성공 로그"""
        message = f"기사 파싱 성공: {title[:50]}... - {url}"
        self.info(message, crawler_name)
    
    def log_article_saved(self, crawler_name: str, title: str, table_name: str):
        """기사 저장 성공 로그"""
        message = f"기사 저장 성공: {title[:50]}... - 테이블: {table_name}"
        self.info(message, crawler_name)
    
    def log_article_skipped(self, crawler_name: str, reason: str, url: str = None):
        """기사 건너뜀 로그"""
        message = f"기사 건너뜀: {reason}"
        if url:
            message += f" - URL: {url}"
        self.warning(message, crawler_name)

# 전역 로거 인스턴스
logger_manager = Logger()

def get_logger(name: str = None) -> logging.Logger:
    """로거 인스턴스 반환 (편의 함수)"""
    return logger_manager.get_logger(name)
