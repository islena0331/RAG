param(
    [string]$File = "docs/test.pdf",
    [string]$Title = "테스트 문서",
    [int]$SecurityLevel = 2,
    [string]$Labels = "테스트",
    [string]$Ocr = "off"
)

docker compose up -d mongo qdrant rag
docker compose exec rag python ingest.py --file $File --title $Title --security-level $SecurityLevel --labels $Labels --ocr $Ocr
