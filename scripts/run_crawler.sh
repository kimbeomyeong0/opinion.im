#!/bin/bash

echo "�� 언론사 크롤러 실행 중..."

# 가상환경 활성화 (선택사항)
# source venv/bin/activate

# 의존성 설치
echo "📦 의존성 설치 중..."
pip install -r requirements.txt

# 기본 크롤러 실행
echo "🔄 기본 크롤러 실행 중..."
python news_crawler.py

echo ""
echo "🎯 고급 크롤러 실행 중..."
python advanced_crawler.py

echo "✅ 모든 크롤러 실행 완료!"
```

```

