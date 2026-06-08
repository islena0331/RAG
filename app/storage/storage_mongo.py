from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.core.config import MONGODB_DB_NAME, MONGODB_URL
from app.core.schemas import DocumentMetadata, RagChunk, dataclass_to_dict


# 청크 직렬화
def _serialize_chunk(chunk: RagChunk) -> dict[str, object]:
    return dataclass_to_dict(chunk)


def save_to_mongodb(
    document: DocumentMetadata,
    chunks: list[RagChunk],
    mongodb_url: str = MONGODB_URL,
    database_name: str = MONGODB_DB_NAME,
) -> tuple[bool, str | None]:
    client: MongoClient | None = None
    document_inserted = False

    try:
        client = MongoClient(mongodb_url, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        database = client[database_name]

        database["rag_documents"].insert_one(dataclass_to_dict(document))
        document_inserted = True
        if chunks:
            database["rag_chunks"].insert_many(
                [_serialize_chunk(chunk) for chunk in chunks]
            )
        return True, None
    except PyMongoError as error:
        if client is not None and document_inserted:
            try:
                database = client[database_name]
                database["rag_documents"].delete_many(
                    {"document_id": document.document_id}
                )
                database["rag_chunks"].delete_many(
                    {"document_id": document.document_id}
                )
            except PyMongoError:
                pass

        message = f"MongoDB 저장에 실패했습니다: {error}"
        print(f"경고: {message}")
        return False, message
    finally:
        if client is not None:
            client.close()
