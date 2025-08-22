# Tests

프로젝트 테스트 코드들입니다.

## 📁 디렉토리 구조

- **`unit/`** - 단위 테스트
- **`integration/`** - 통합 테스트  
- **`debug/`** - 디버깅 테스트

## 🧪 테스트 유형

### Unit Tests (`unit/`)
- 개별 함수/클래스 테스트
- 모듈별 독립적 테스트
- 빠른 실행 및 디버깅

### Integration Tests (`integration/`)
- 모듈 간 연동 테스트
- 전체 워크플로우 테스트
- 데이터베이스 연동 테스트

### Debug Tests (`debug/`)
- 크롤링 로직 검증
- HTML 구조 분석
- 에러 상황 테스트

## 🚀 실행 방법

```bash
# 전체 테스트 실행
python -m pytest tests/

# 특정 테스트 실행
python -m pytest tests/unit/
python -m pytest tests/integration/
python -m pytest tests/debug/

# 디버그 테스트 직접 실행
python tests/debug/debug_chosun.py
```

## 📊 테스트 커버리지

- 크롤러 기능 검증
- 데이터 처리 로직 검증
- 에러 처리 검증
- 성능 및 안정성 검증
