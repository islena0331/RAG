## 설치

python -m venv .venv-rag
.\.venv-rag\Scripts\Activate.ps1
python -m pip install -r requirements-rag.txt


별도 설치 필요
- Tesseract OCR
- Poppler
- 한국어 OCR용 `kor.traineddata`

## 실행

JSON 저장
python main.py --file docs/test.pdf --title "테스트 문서" --security-level 2 --labels 작전,장비 --ocr auto --storage json


JSON 및 MongoDB 저장
python main.py --file docs/test.pdf --title "테스트 문서" --security-level 2 --labels 작전,장비 --ocr auto --storage both


MongoDB 저장
python main.py --file docs/test.pdf --title "테스트 문서" --security-level 2 --labels 작전,장비 --ocr auto --storage mongo


## CLI 옵션

| 옵션 | 값 | 설명 |
| `--file` | PDF 경로 | 처리할 로컬 PDF |
| `--title` | 문자열 | 문서 제목 |
| `--security-level` | `1`, `2`, `3` | 보안 등급 |
| `--labels` | 쉼표 구분 문자열 | 청크 라벨 |
| `--ocr` | `off`, `auto`, `force` | OCR 실행 방식 |
| `--storage` | `json`, `mongo`, `both` | 저장 대상 |

OCR 모드
- `off`: `pypdf`만 사용
- `auto`: 추출 텍스트가 부족한 페이지만 OCR
- `force`: 모든 페이지 OCR



## 출력

JSON
outputs/{document_id}_document.json
outputs/{document_id}_chunks.json


MongoDB
URL: mongodb://localhost:27018
DB: rag_prototype
Collections:
  rag_documents
  rag_chunks



## 청크 필드

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
  "created_at": "..."
}

- `page_number`: 대표 페이지
- `page_numbers`: 청크에 포함된 전체 페이지
- `is_noisy`: 명단, 숫자 표, 반복 OCR 패턴 여부
- `is_title`: 표지, 제목, 짧은 핵심 문장 여부



## Summary

실행 완료 후 출력 항목
- `document_id`
- `title`
- `original_filename`
- `security_level`
- `total_pages`
- `extracted_pages`
- `chunk_count`
- `noisy_chunk_count`
- `title_chunk_count`
- `skipped_pages`
- JSON 저장 경로
- MongoDB 저장 결과


skipped_pages 사유
- `no_text`
- `image_only`
- `empty_after_cleaning`
- `too_short`
- `duplicate`



## MongoDB 확인

python -c "from pymongo import MongoClient; c=MongoClient('mongodb://localhost:27018'); db=c['rag_prototype']; print(db.list_collection_names()); print(db['rag_documents'].count_documents({})); print(db['rag_chunks'].count_documents({}))"
