## 설치

```powershell
python -m venv .venv-rag
.\.venv-rag\Scripts\Activate.ps1
python -m pip install -r requirements-rag.txt
Copy-Item .env.example .env
```

OCR 사용 시 별도 설치 필요
- Tesseract OCR
- Poppler



## MongoDB 실행

```powershell
docker run -d --name rag-mongodb -p 27018:27017 -v rag_mongodb_storage:/data/db mongo
```

기존 컨테이너 실행
```powershell
docker start rag-mongodb
```

## Qdrant 실행

```powershell
docker run -d --name rag-qdrant -p 6333:6333 -p 6334:6334 -v rag_qdrant_storage:/qdrant/storage qdrant/qdrant
```

기존 컨테이너 실행
```powershell
docker start rag-qdrant
```

Dashboard
```text
http://localhost:6333/dashboard
```

## PDF 전처리

JSON 저장
```powershell
python main.py --file docs/test.pdf --title "테스트 문서" --security-level 2 --labels 작전,장비 --ocr off --storage json
```

JSON과 MongoDB 저장
```powershell
python main.py --file docs/test.pdf --title "테스트 문서" --security-level 2 --labels 작전,장비 --ocr off --storage both
```

OCR 모드
- `off`: pypdf만 사용
- `auto`: 텍스트가 부족한 페이지만 OCR
- `force`: 모든 페이지 OCR

## 임베딩

BAAI/bge-m3 모델은 첫 실행 시 자동으로 다운로드됨
첫 실행은 오래 걸릴 수 있으며 이후에는 로컬 캐시 사용

20개 테스트
```powershell
python embed_to_qdrant.py --limit 20
```

전체 임베딩
```powershell
python embed_to_qdrant.py
```

특정 문서
```powershell
python embed_to_qdrant.py --document-id 문서ID
```

선택 옵션
```powershell
python embed_to_qdrant.py --include-noisy
python embed_to_qdrant.py --include-title
python embed_to_qdrant.py --force
python embed_to_qdrant.py --recreate-collection
```

기본 제외 대상
- `is_noisy=true`
- `is_title=true`
- 현재 모델로 이미 임베딩된 chunk
- 빈 `chunk_text`

## 검색

```powershell
python search_qdrant.py --query "북한 핵전략은 무엇인가?"
python search_qdrant.py --query "확장억제" --top-k 5
python search_qdrant.py --query "북한 비핵화 노력" --security-level 2
```

## 저장 역할

MongoDB
- 문서 metadata
- chunk 원문
- `page_numbers`, `security_level`, `labels`
- `is_noisy`, `is_title`
- 임베딩 완료 상태와 모델 정보

Qdrant
- chunk embedding vector
- 검색용 payload
- cosine similarity search

Embedding vector는 MongoDB에 저장하지 않음

## MongoDB 임베딩 상태 필드

```json
{
  "embedded": true,
  "embedded_at": "...",
  "embedding_model": "BAAI/bge-m3",
  "vector_db": "qdrant",
  "qdrant_collection": "rag_chunks_bge_m3",
  "vector_id": "chunk_id"
}
```
## Qdrant payload

```json
{
  "chunk_id": "...",
  "document_id": "...",
  "chunk_index": 0,
  "chunk_text": "...",
  "page_number": 2,
  "page_numbers": [1, 2],
  "security_level": 2,
  "labels": ["작전", "장비"],
  "extraction_method": "pypdf",
  "is_noisy": false,
  "is_title": false,
  "created_at": "...",
  "embedding_model": "BAAI/bge-m3"
}
```
