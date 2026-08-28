from qdrant_client import QdrantClient, models

from backend.app.storage import VectorStorage


def point(point_id: int, source: str) -> models.PointStruct:
    return models.PointStruct(
        id=point_id,
        vector={"dense": [0.0] * 384},
        payload={"source": source},
    )


def test_delete_all_documents_preserves_a_reusable_empty_collection(tmp_path):
    storage = VectorStorage.__new__(VectorStorage)
    storage.collection_name = "test_collection"
    storage.client = QdrantClient(path=str(tmp_path / "qdrant"))

    try:
        storage._init_collection()

        storage.delete_all_documents()
        assert storage.client.collection_exists(storage.collection_name)
        assert storage.client.count(storage.collection_name, exact=True).count == 0

        storage.client.upsert(
            collection_name=storage.collection_name,
            points=[point(1, "document-1"), point(2, "document-2")],
            wait=True,
        )
        assert storage.client.count(storage.collection_name, exact=True).count == 2

        storage.delete_all_documents()
        points, _ = storage.client.scroll(
            collection_name=storage.collection_name,
            limit=10,
        )
        assert points == []
        assert storage.client.collection_exists(storage.collection_name)

        storage.client.upsert(
            collection_name=storage.collection_name,
            points=[point(3, "document-3")],
            wait=True,
        )
        assert storage.client.count(storage.collection_name, exact=True).count == 1
    finally:
        storage.client.close()


def test_delete_document_preserves_other_documents(tmp_path):
    storage = VectorStorage.__new__(VectorStorage)
    storage.collection_name = "test_collection"
    storage.client = QdrantClient(path=str(tmp_path / "qdrant"))

    try:
        storage._init_collection()
        storage.client.upsert(
            collection_name=storage.collection_name,
            points=[
                point(1, "remove.pdf"),
                point(2, "remove.pdf"),
                point(3, "keep.pdf"),
            ],
            wait=True,
        )

        storage.delete_document("remove.pdf")

        remaining, _ = storage.client.scroll(
            collection_name=storage.collection_name,
            limit=10,
            with_payload=True,
        )
        assert [item.payload["source"] for item in remaining] == ["keep.pdf"]
    finally:
        storage.client.close()
