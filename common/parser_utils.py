#!/usr/bin/env python3
"""
공통 HTML 파싱 유틸리티
날짜 파싱, 제목 정리, 본문 추출, 광고/기자명 제거 등의 공통 기능 제공
"""

import re
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup, Tag

class ParserUtils:
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
        
        # 불필요한 문자 제거
        title = re.sub(r'[\[\]【】]', '', title)  # 대괄호 제거
        title = re.sub(r'[^\w\s가-힣\-\.\,\:\!\?]', '', title)  # 특수문자 제거
        
        # 연속된 공백을 하나로
        title = re.sub(r'\s+', ' ', title)
        
        return title.strip()
    
    @staticmethod
    def clean_content(content: str) -> str:
        """
        기사 본문 정리 (광고, 기자명 등 제거)
        
        Args:
            content: 원본 본문
        
        Returns:
            정리된 본문
        """
        if not content:
            return ""
        
        # 광고 관련 텍스트 제거
        ad_patterns = [
            r'\[.*?광고.*?\]',
            r'\(.*?광고.*?\)',
            r'<.*?광고.*?>',
            r'광고\s*문의',
            r'광고\s*제휴',
            r'스폰서',
            r'협찬',
        ]
        
        for pattern in ad_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        # 기자명 관련 텍스트 제거
        reporter_patterns = [
            r'기자\s*[가-힣]+\s*기자',
            r'[가-힣]+\s*기자',
            r'기자\s*[가-힣]+',
            r'취재\s*[가-힣]+',
            r'[가-힣]+\s*취재',
        ]
        
        for pattern in reporter_patterns:
            content = re.sub(pattern, '', content)
        
        # 불필요한 공백 정리
        content = re.sub(r'\n\s*\n', '\n\n', content)  # 연속된 빈 줄을 2개로
        content = re.sub(r'^\s+', '', content, flags=re.MULTILINE)  # 줄 시작 공백 제거
        content = re.sub(r'\s+$', '', content, flags=re.MULTILINE)  # 줄 끝 공백 제거
        
        return content.strip()
    
    @staticmethod
    def extract_text_from_html(html_content: str) -> str:
        """
        HTML에서 텍스트만 추출
        
        Args:
            html_content: HTML 문자열
        
        Returns:
            추출된 텍스트
        """
        if not html_content:
            return ""
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # script, style 태그 제거
            for script in soup(["script", "style"]):
                script.decompose()
            
            # 텍스트 추출
            text = soup.get_text()
            
            # 연속된 공백과 줄바꿈 정리
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text
            
        except Exception:
            # HTML 파싱 실패 시 정규식으로 태그 제거
            text = re.sub(r'<[^>]+>', '', html_content)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
    
    @staticmethod
    def extract_author(text: str) -> Optional[str]:
        """
        텍스트에서 기자명 추출
        
        Args:
            text: 검색할 텍스트
        
        Returns:
            추출된 기자명 또는 None
        """
        if not text:
            return None
        
        # 기자명 패턴들
        author_patterns = [
            r'([가-힣]+)\s*기자',
            r'기자\s*([가-힣]+)',
            r'([가-힣]+)\s*취재',
            r'취재\s*([가-힣]+)',
        ]
        
        for pattern in author_patterns:
            match = re.search(pattern, text)
            if match:
                author = match.group(1).strip()
                if len(author) >= 2:  # 2글자 이상만 유효한 기자명으로 간주
                    return author
        
        return None
