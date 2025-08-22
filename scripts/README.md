# Scripts

크롤러 실행을 위한 스크립트들입니다.

## 📁 파일 목록

- `run_chosun_crawler.sh` - 조선일보 크롤러 실행
- `run_chosun_politics.sh` - 조선일보 정치 기사 크롤러 실행
- `run_crawler.sh` - 전체 크롤러 실행
- `run_supabase_crawler.sh` - Supabase 연동 크롤러 실행

## 🔧 사용법

```bash
# 스크립트 실행 권한 부여
chmod +x *.sh

# 조선일보 정치 기사 크롤링
./run_chosun_politics.sh

# 전체 크롤러 실행
./run_crawler.sh
```

## ⚠️ 주의사항

- 실행 전 Python 환경과 의존성이 설치되어 있어야 합니다
- 각 스크립트는 독립적으로 실행할 수 있습니다
