# Debug

디버깅 및 테스트를 위한 파일들입니다.

## 📁 파일 목록

### Python 디버그 파일
- `debug_article.py` - 기사 디버깅
- `debug_chosun.py` - 조선일보 디버깅
- `debug_donga.py` - 동아일보 디버깅
- `debug_donga_article.py` - 동아일보 기사 디버깅
- `debug_donga_article_full.py` - 동아일보 기사 전체 디버깅
- `debug_pressian_simple.py` - 프레시안 간단 디버깅
- `debug_pressian_structure.py` - 프레시안 구조 디버깅

### HTML 디버그 파일
- `chosun_article_debug.html` - 조선일보 기사 HTML 디버그
- `chosun_politics_debug.html` - 조선일보 정치 기사 HTML 디버그

## 🔧 사용법

```bash
# 특정 언론사 디버깅
python debug/debug_chosun.py

# HTML 구조 분석
open debug/chosun_politics_debug.html
```

## 📊 목적

- 크롤링 로직 검증
- HTML 구조 분석
- 에러 원인 파악
- 크롤링 품질 확인
