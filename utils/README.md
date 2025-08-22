# Utils

공통 유틸리티 모듈들입니다.

## 📁 파일 목록

- `supabase_manager.py` - Supabase 데이터베이스 관리 (v1, 뉴스 데이터 전용)
- `supabase_manager_v2.py` - Supabase 데이터베이스 관리 (v2, 이슈 분석 전용)
- `supabase_manager_unified.py` - **통합된 Supabase 매니저 (권장)**
- `test_donga_content.py` - 동아일보 콘텐츠 테스트

## 🔧 주요 기능

### Supabase Manager (v1) - 뉴스 데이터 관리
- 뉴스 기사 저장 및 관리
- `chosun_politics_news` 테이블 전용
- 기본적인 CRUD 작업

### Supabase Manager (v2) - 이슈 분석 관리
- 이슈별 편향성 분석
- 편향성 요약 저장
- 미디어별 요약 관리

### **UnifiedSupabaseManager (통합) - 권장**
- **뉴스 데이터 + 이슈 분석 통합 관리**
- 하나의 클래스로 모든 기능 제공
- 프로젝트 전체 상태 모니터링
- 코드 중복 제거 및 유지보수성 향상

## 📊 사용법

### 통합 매니저 사용 (권장)
```python
from utils.supabase_manager_unified import UnifiedSupabaseManager

# 통합 매니저 초기화
manager = UnifiedSupabaseManager()

# 뉴스 데이터 관리
manager.insert_news(news_data)
news_count = manager.get_news_count()

# 이슈 분석 관리
issue_id = manager.create_issue("정치 이슈", "부동산 정책")
manager.update_issue_bias(issue_id, {'left': 3, 'center': 2, 'right': 1})

# 프로젝트 상태 확인
manager.display_status()
```

### 기존 매니저 사용 (레거시)
```python
from utils.supabase_manager import SupabaseManager
from utils.supabase_manager_v2 import SupabaseManagerV2

# 뉴스 데이터용
news_manager = SupabaseManager()
news_manager.insert_news(news_data)

# 이슈 분석용
issue_manager = SupabaseManagerV2()
issue_manager.create_issue("이슈 제목")
```

## 🔄 마이그레이션 가이드

기존 코드를 통합 매니저로 마이그레이션하려면:

1. `UnifiedSupabaseManager`로 import 변경
2. 메서드 호출 방식은 동일 (호환성 유지)
3. 추가 기능 활용 (상태 모니터링 등)

## ⚠️ 주의사항

- **새로운 프로젝트는 통합 매니저 사용 권장**
- 기존 코드는 점진적으로 마이그레이션
- 환경변수 설정 필요 (`SUPABASE_URL`, `SUPABASE_KEY`)
