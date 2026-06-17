param(
    [Parameter(Mandatory = $true)]
    [string]$Query,
    [int]$UserSecurityLevel = 2
)

docker compose up -d mongo qdrant rag
docker compose exec rag python rag_answer.py --query $Query --user-security-level $UserSecurityLevel
