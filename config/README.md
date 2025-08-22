# Config

프로젝트 설정 파일들입니다.

## 📁 파일 목록

- `config.py` - 기본 설정 (데이터베이스, API 키 등)
- `config_chosun.py` - 조선일보 전용 설정

## 🔧 설정 항목

### 기본 설정 (`config.py`)
- Supabase 연결 정보
- API 키 및 엔드포인트
- 기본 크롤링 설정

### 조선일보 설정 (`config_chosun.py`)
- 조선일보 전용 URL 패턴
- 크롤링 규칙 및 선택자
- 특별한 처리 로직

## 📝 사용법

```python
from config.config import Config
from config.config_chosun import ChosunConfig

# 기본 설정 로드
config = Config()

# 조선일보 설정 로드
chosun_config = ChosunConfig()
```

## ⚠️ 보안

- API 키와 민감한 정보는 환경변수로 관리
- `.env` 파일을 통한 설정 관리 권장
