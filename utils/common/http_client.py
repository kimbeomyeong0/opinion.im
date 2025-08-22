#!/usr/bin/env python3
"""
공통 HTTP 클라이언트 유틸리티
다양한 HTTP 라이브러리 (httpx, aiohttp)를 통합 관리
"""

import asyncio
from typing import Optional, Dict, Any, Union
import httpx
import aiohttp
from rich.console import Console

console = Console()


class HTTPClientManager:
    """통합 HTTP 클라이언트 매니저"""
    
    def __init__(self, client_type: str = "httpx", timeout: float = 10.0):
        """
        Args:
            client_type: "httpx" 또는 "aiohttp"
            timeout: 요청 타임아웃 (초)
        """
        self.client_type = client_type
        self.timeout = timeout
        self.session = None
        
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        if self.client_type == "aiohttp":
            connector = aiohttp.TCPConnector(limit=20, limit_per_host=10)
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=self._get_default_headers()
            )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.session:
            await self.session.close()
    
    def _get_default_headers(self) -> Dict[str, str]:
        """기본 HTTP 헤더 반환"""
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.8,en-US;q=0.5,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
    
    async def get(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[str]:
        """HTTP GET 요청 수행"""
        try:
            if self.client_type == "httpx":
                return await self._httpx_get(url, params, headers)
            elif self.client_type == "aiohttp":
                return await self._aiohttp_get(url, params, headers)
            else:
                raise ValueError(f"지원하지 않는 클라이언트 타입: {self.client_type}")
                
        except Exception as e:
            console.print(f"❌ HTTP GET 요청 오류: {str(e)} - {url}")
            return None
    
    async def post(self, url: str, data: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[str]:
        """HTTP POST 요청 수행"""
        try:
            if self.client_type == "httpx":
                return await self._httpx_post(url, data, headers)
            elif self.client_type == "aiohttp":
                return await self._aiohttp_post(url, data, headers)
            else:
                raise ValueError(f"지원하지 않는 클라이언트 타입: {self.client_type}")
                
        except Exception as e:
            console.print(f"❌ HTTP POST 요청 오류: {str(e)} - {url}")
            return None
    
    async def _httpx_get(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[str]:
        """httpx를 사용한 GET 요청"""
        try:
            async with httpx.AsyncClient(
                headers=headers or self._get_default_headers(),
                timeout=self.timeout,
                follow_redirects=True
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.text
                
        except httpx.HTTPStatusError as e:
            console.print(f"❌ HTTP 오류: {e.response.status_code} - {url}")
            return None
        except httpx.TimeoutException:
            console.print(f"⏰ 타임아웃: {url}")
            return None
        except Exception as e:
            console.print(f"❌ httpx GET 요청 오류: {str(e)} - {url}")
            return None
    
    async def _httpx_post(self, url: str, data: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[str]:
        """httpx를 사용한 POST 요청"""
        try:
            async with httpx.AsyncClient(
                headers=headers or self._get_default_headers(),
                timeout=self.timeout,
                follow_redirects=True
            ) as client:
                response = await client.post(url, data=data)
                response.raise_for_status()
                return response.text
                
        except httpx.HTTPStatusError as e:
            console.print(f"❌ HTTP 오류: {e.response.status_code} - {url}")
            return None
        except httpx.TimeoutException:
            console.print(f"⏰ 타임아웃: {url}")
            return None
        except Exception as e:
            console.print(f"❌ httpx POST 요청 오류: {str(e)} - {url}")
            return None
    
    async def _aiohttp_get(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[str]:
        """aiohttp를 사용한 GET 요청"""
        try:
            if not self.session:
                raise RuntimeError("aiohttp 세션이 초기화되지 않았습니다. 컨텍스트 매니저를 사용하세요.")
            
            async with self.session.get(url, params=params, headers=headers) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    console.print(f"❌ HTTP 오류: {response.status} - {url}")
                    return None
                    
        except Exception as e:
            console.print(f"❌ aiohttp GET 요청 오류: {str(e)} - {url}")
            return None
    
    async def _aiohttp_post(self, url: str, data: Optional[Dict] = None, headers: Optional[Dict] = None) -> Optional[str]:
        """aiohttp를 사용한 POST 요청"""
        try:
            if not self.session:
                raise RuntimeError("aiohttp 세션이 초기화되지 않았습니다. 컨텍스트 매니저를 사용하세요.")
            
            async with self.session.post(url, data=data, headers=headers) as response:
                if response.status == 200:
                    return await response.text()
                else:
                    console.print(f"❌ HTTP 오류: {response.status} - {url}")
                    return None
                    
        except Exception as e:
            console.print(f"❌ aiohttp POST 요청 오류: {str(e)} - {url}")
            return None


# 편의 함수들
async def make_request(url: str, client_type: str = "httpx", method: str = "GET", 
                      params: Optional[Dict] = None, data: Optional[Dict] = None, 
                      headers: Optional[Dict] = None, timeout: float = 10.0) -> Optional[str]:
    """
    간단한 HTTP 요청 함수
    
    Args:
        url: 요청할 URL
        client_type: "httpx" 또는 "aiohttp"
        method: "GET" 또는 "POST"
        params: GET 요청 파라미터
        data: POST 요청 데이터
        headers: HTTP 헤더
        timeout: 타임아웃 (초)
    
    Returns:
        응답 텍스트 또는 None (실패 시)
    """
    async with HTTPClientManager(client_type, timeout) as client:
        if method.upper() == "GET":
            return await client.get(url, params, headers)
        elif method.upper() == "POST":
            return await client.post(url, data, headers)
        else:
            raise ValueError(f"지원하지 않는 HTTP 메서드: {method}")


async def make_requests_batch(urls: list, client_type: str = "httpx", 
                             method: str = "GET", max_concurrent: int = 10, 
                             delay: float = 0.1) -> Dict[str, Optional[str]]:
    """
    여러 URL에 대한 배치 요청
    
    Args:
        urls: 요청할 URL 리스트
        client_type: "httpx" 또는 "aiohttp"
        method: "GET" 또는 "POST"
        max_concurrent: 최대 동시 요청 수
        delay: 요청 간 지연 (초)
    
    Returns:
        URL별 응답 결과 딕셔너리
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = {}
    
    async def fetch_with_semaphore(url):
        async with semaphore:
            result = await make_request(url, client_type, method)
            await asyncio.sleep(delay)
            return url, result
    
    tasks = [fetch_with_semaphore(url) for url in urls]
    completed = await asyncio.gather(*tasks, return_exceptions=True)
    
    for url, result in completed:
        if isinstance(result, Exception):
            results[url] = None
            console.print(f"❌ {url} 요청 실패: {str(result)}")
        else:
            results[url] = result
    
    return results
