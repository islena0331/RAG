## 설치

python -m venv .venv-rag
.\.venv-rag\Scripts\Activate.ps1
python -m pip install -r requirements-rag.txt
Copy-Item .env.example .env

OCR을 사용하려면 Tesseract OCR, Poppler 설치 필요



## 실행 준비

MongoDB URL: `mongodb://localhost:27018`

MongoDB:
docker run -d --name rag-mongo -p 27018:27017 -v rag_mongodb_storage:/data/db mongo

Qdrant:
docker run -d --name rag-qdrant -p 6333:6333 -p 6334:6334 -v rag_qdrant_storage:/qdrant/storage qdrant/qdrant

기존 컨테이너 실행:
docker start rag-mongo rag-qdrant

Qdrant Dashboard:
http://localhost:6333/dashboard




## 환경변수

주요 설정:
| 설정 | 기본값 | 용도 |
| `OPENAI_MODEL` | `gpt-4o-mini` | 답변 모델 |
| `RAG_TOP_K` | `5` | 최종 검색 청크 수 |
| `RAG_SCORE_THRESHOLD` | 빈 값 | 최소 검색 점수 |
| `RAG_MAX_CONTEXT_TOKENS` | `12000` | 문서 context 상한 |
| `RAG_MAX_CHUNKS_PER_DOCUMENT` | `2` | 문서별 우선 선택 수 |



## 구조

- `ingest.py`: PDF 적재 전체 실행
- `rag_answer.py`: 검색과 답변 실행
- `scripts/`: 단계별 실행과 점검 명령
- `app/core/`: 설정과 공통 구조
- `app/services/`: 전처리, 임베딩, 검색, 답변 로직
- `app/storage/`: JSON, MongoDB, Qdrant 저장



## 사용 순서

### 1. 전체 적재

python ingest.py --file docs/test.pdf --title "테스트 문서" --security-level 2 --labels 작전,장비 --ocr off

처리 순서:
- PDF 텍스트 추출
- 텍스트 정제와 청킹
- JSON과 MongoDB 저장
- 임베딩 생성
- Qdrant 저장

OCR 모드:
- `off`: PDF 텍스트만 사용
- `auto`: 필요한 페이지만 OCR
- `force`: 모든 페이지 OCR


### 2. RAG 질의

python rag_answer.py --query "북한의 핵전략은 무엇인가?" --user-security-level 2

API 호출 없이 검색 결과 확인:
python rag_answer.py --query "북한의 핵전략은 무엇인가?" --user-security-level 2 --dry-run --show-context

검색 설정 변경:
python rag_answer.py --query "질문" --user-security-level 2 --top-k 3 --score-threshold 0.5



## 개별 실행

PDF 저장만 실행:
python -m scripts.preprocess_pdf --file docs/test.pdf --title "테스트 문서" --security-level 2 --labels 작전,장비 --ocr off --storage both

Qdrant 임베딩만 실행:

테스트:
python -m scripts.embed_to_qdrant --limit 20

전체:
python -m scripts.embed_to_qdrant

특정 문서:
python -m scripts.embed_to_qdrant --document-id 문서ID

이미 임베딩된 청크는 건너뜀

Qdrant 검색만 확인:
python -m scripts.search_qdrant --query "질문" --security-level 2


## 기타

- `--include-noisy`: noisy 청크 포함
- `--debug`: 토큰과 제외 source 출력
- `--guard-on`: guardrail 연결점 실행
