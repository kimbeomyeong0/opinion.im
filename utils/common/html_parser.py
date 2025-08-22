#!/usr/bin/env python3
"""
공통 HTML 파싱 유틸리티
날짜 파싱, 제목 정리, 본문 추출 등의 공통 기능 제공
"""

import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup, Tag
from rich.console import Console

console = Console()


class HTMLParserUtils:
    """HTML 파싱 공통 유틸리티"""
    
    @staticmethod
    def parse_date(date_str: str, patterns: Optional[List[str]] = None) -> Optional[str]:
        """
        다양한 날짜 형식을 YYYY-MM-DD 형식으로 변환
        
        Args:
            date_str: 파싱할 날짜 문자열
            patterns: 사용할 정규식 패턴 리스트 (기본값 사용 시 None)
        
        Returns:
            YYYY-MM-DD 형식의 날짜 문자열 또는 None
        """
        if not date_str:
            return None
        
        # 기본 패턴들
        default_patterns = [
            # 한국어 날짜 형식
            r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일',  # 2025년 8월 22일
            r'(\d{1,2})월\s*(\d{1,2})일',  # 8월 22일 (올해로 가정)
            
            # 점 구분 형식
            r'(\d{4})\.(\d{1,2})\.(\d{1,2})',  # 2025.08.22
            r'(\d{2})\.(\d{1,2})\.(\d{1,2})',  # 25.08.22 (20xx년으로 가정)
            r'(\d{1,2})\.(\d{1,2})\.(\d{1,2})',  # 08.22 (올해로 가정)
            
            # 하이픈 구분 형식
            r'(\d{4})-(\d{1,2})-(\d{1,2})',  # 2025-08-22
            r'(\d{2})-(\d{1,2})-(\d{1,2})',  # 25-08-22 (20xx년으로 가정)
            
            # 슬래시 구분 형식
            r'(\d{4})/(\d{1,2})/(\d{1,2})',  # 2025/08/22
            r'(\d{2})/(\d{1,2})/(\d{1,2})',  # 25/08/22 (20xx년으로 가정)
            
            # 공백 구분 형식
            r'(\d{4})\s+(\d{1,2})\s+(\d{1,2})',  # 2025 08 22
            r'(\d{2})\s+(\d{1,2})\s+(\d{1,2})',  # 25 08 22 (20xx년으로 가정)
        ]
        
        patterns = patterns or default_patterns
        
        for pattern in patterns:
            match = re.search(pattern, date_str)
            if match:
                groups = match.groups()
                if len(groups) == 3:
                    year, month, day = groups
                    
                    # 년도 처리
                    if len(year) == 2:
                        year = f"20{year}"  # 25 -> 2025
                    elif len(year) == 4:
                        year = year  # 2025 -> 2025
                    else:
                        continue
                    
                    # 월/일 처리
                    try:
                        month = int(month)
                        day = int(day)
                        
                        if 1 <= month <= 12 and 1 <= day <= 31:
                            return f"{year}-{month:02d}-{day:02d}"
                    except ValueError:
                        continue
        
        return None
    
    @staticmethod
    def clean_title(title: str) -> str:
        """
        기사 제목 정리
        
        Args:
            title: 원본 제목
        
        Returns:
            정리된 제목
        """
        if not title:
            return ""
        
        # HTML 태그 제거
        title = re.sub(r'<[^>]+>', '', title)
        
        # 특수 문자 정리
        title = re.sub(r'[^\w\s가-힣\-\.\,\?\!\(\)\[\]\'\"]', '', title)
        
        # 연속 공백 정리
        title = re.sub(r'\s+', ' ', title)
        
        # 앞뒤 공백 제거
        title = title.strip()
        
        # 제목 길이 제한 (너무 긴 제목은 잘라내기)
        if len(title) > 200:
            title = title[:200] + "..."
        
        return title
    
    @staticmethod
    def extract_text_content(element: Tag, selectors: List[str]) -> str:
        """
        여러 선택자를 시도하여 텍스트 내용 추출
        
        Args:
            element: BeautifulSoup 요소
            selectors: 시도할 CSS 선택자 리스트
        
        Returns:
            추출된 텍스트
        """
        for selector in selectors:
            try:
                found = element.select_one(selector)
                if found:
                    text = found.get_text(separator='\n', strip=True)
                    if text:
                        return text
            except Exception:
                continue
        
        return ""
    
    @staticmethod
    def extract_article_content(html: str, content_selectors: List[str], 
                               title_selectors: Optional[List[str]] = None,
                               date_selectors: Optional[List[str]] = None) -> Dict[str, str]:
        """
        기사 내용 추출 (제목, 본문, 날짜)
        
        Args:
            html: HTML 문자열
            content_selectors: 본문 추출용 CSS 선택자 리스트
            title_selectors: 제목 추출용 CSS 선택자 리스트
            date_selectors: 날짜 추출용 CSS 선택자 리스트
        
        Returns:
            추출된 내용 딕셔너리
        """
        soup = BeautifulSoup(html, 'html.parser')
        result = {
            'title': '',
            'content': '',
            'date': ''
        }
        
        # 본문 추출
        if content_selectors:
            result['content'] = HTMLParserUtils.extract_text_content(soup, content_selectors)
        
        # 제목 추출
        if title_selectors:
            title_text = HTMLParserUtils.extract_text_content(soup, title_selectors)
            result['title'] = HTMLParserUtils.clean_title(title_text)
        
        # 날짜 추출
        if date_selectors:
            date_text = HTMLParserUtils.extract_text_content(soup, date_selectors)
            result['date'] = HTMLParserUtils.parse_date(date_text) or ''
        
        return result
    
    @staticmethod
    def find_links_with_pattern(element: Tag, pattern: str, base_url: str = "") -> List[str]:
        """
        특정 패턴을 가진 링크들 찾기
        
        Args:
            element: BeautifulSoup 요소
            pattern: 링크 URL 패턴 (정규식)
            base_url: 상대 경로를 절대 경로로 변환할 기본 URL
        
        Returns:
            찾은 링크 리스트
        """
        links = []
        
        try:
            # 모든 a 태그 찾기
            for link in element.find_all('a', href=True):
                href = link.get('href')
                if href and re.search(pattern, href):
                    # 상대 경로를 절대 경로로 변환
                    if href.startswith('/'):
                        full_url = base_url + href
                    elif href.startswith('http'):
                        full_url = href
                    else:
                        full_url = base_url + '/' + href
                    
                    links.append(full_url)
        except Exception as e:
            console.print(f"❌ 링크 추출 오류: {str(e)}")
        
        return links
    
    @staticmethod
    def remove_ads_and_scripts(html: str) -> str:
        """
        광고와 스크립트 태그 제거
        
        Args:
            html: 원본 HTML
        
        Returns:
            정리된 HTML
        """
        soup = BeautifulSoup(html, 'html.parser')
        
        # 광고 관련 태그 제거
        ad_selectors = [
            '[class*="ad"]', '[class*="advertisement"]', '[class*="banner"]',
            '[id*="ad"]', '[id*="advertisement"]', '[id*="banner"]',
            'iframe[src*="ad"]', 'iframe[src*="banner"]'
        ]
        
        for selector in ad_selectors:
            for element in soup.select(selector):
                element.decompose()
        
        # 스크립트 태그 제거
        for script in soup.find_all('script'):
            script.decompose()
        
        # 스타일 태그 제거
        for style in soup.find_all('style'):
            style.decompose()
        
        return str(soup)


# 편의 함수들
def parse_date_simple(date_str: str) -> Optional[str]:
    """간단한 날짜 파싱 함수"""
    return HTMLParserUtils.parse_date(date_str)


def clean_title_simple(title: str) -> str:
    """간단한 제목 정리 함수"""
    return HTMLParserUtils.clean_title(title)


def extract_content_simple(html: str, content_selector: str) -> str:
    """간단한 본문 추출 함수"""
    return HTMLParserUtils.extract_article_content(
        html, 
        [content_selector]
    )['content']


# 날짜 관련 유틸리티
def get_date_range(days: int = 7) -> List[str]:
    """
    최근 N일의 날짜 리스트 반환
    
    Args:
        days: 가져올 일수
    
    Returns:
        YYYY-MM-DD 형식의 날짜 리스트
    """
    dates = []
    today = datetime.now()
    
    for i in range(days):
        date = today - timedelta(days=i)
        dates.append(date.strftime("%Y-%m-%d"))
    
    return dates


def is_recent_date(date_str: str, days: int = 7) -> bool:
    """
    날짜가 최근 N일 내인지 확인
    
    Args:
        date_str: 확인할 날짜 (YYYY-MM-DD 형식)
        days: 기준 일수
    
    Returns:
        최근 N일 내이면 True
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
        today = datetime.now()
        diff = today - target_date
        
        return diff.days <= days
    except ValueError:
        return False
