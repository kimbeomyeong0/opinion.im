# Legacy Files

레거시 Supabase 매니저 파일들입니다.

## ⚠️ 주의사항

**이 파일들은 더 이상 사용되지 않습니다.**
새로운 프로젝트에서는 `supabase_manager_unified.py`를 사용하세요.

## 📁 파일 목록

- `supabase_manager.py` - 뉴스 데이터 관리 (v1)
- `supabase_manager_v2.py` - 이슈 분석 관리 (v2)

## 🔄 마이그레이션 가이드

### 기존 코드를 통합 매니저로 변경:

```python
# 이전 (레거시)
from utils.supabase_manager import SupabaseManager
from utils.supabase_manager_v2 import SupabaseManagerV2

# 새로운 방식 (권장)
from utils.supabase_manager_unified import UnifiedSupabaseManager
```

### 기능 매핑:

| 레거시 | 통합 매니저 |
|--------|-------------|
| `SupabaseManager.insert_news()` | `UnifiedSupabaseManager.insert_news()` |
| `SupabaseManagerV2.create_issue()` | `UnifiedSupabaseManager.create_issue()` |

## 🗑️ 삭제 예정

- 향후 버전에서 완전 제거 예정
- 호환성을 위해 임시 보관
- 마이그레이션 완료 후 삭제 권장
