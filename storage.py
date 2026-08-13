import os
from qdrant_client import QdrantClient, models
from fastembed import TextEmbedding, SparseTextEmbedding

class VectorStorage:
    def __init__(self, collection_name: str = "rag_collection"):
        self.collection_name = collection_name
        self.client = QdrantClient(path="./qdrant_data")
        
        print("Loading local dense & sparse embedding models...")
        self.embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
        self.sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
        
        self._init_collection()

    def _init_collection(self):
        if not self.client.collection_exists(self.collection_name):
            print(f"Creating collection '{self.collection_name}' with Hybrid Search support...")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config={
                    "dense": models.VectorParams(size=384, distance=models.Distance.COSINE)
                },
                sparse_vectors_config={
                    "sparse": models.SparseVectorParams()
                }
            )

    def delete_all_documents(self):
        """Wipes all documents in the collection."""
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.Filter(),
            wait=True
        )

    def add_chunks(self, chunks: list):
        if not chunks:
            print("No chunks to add.")
            return

        texts = [chunk.text for chunk in chunks]
        
        print(f"Embedding {len(chunks)} chunks (Dense & Sparse)...")
        dense_embeddings = list(self.embedding_model.embed(texts))
        sparse_embeddings = list(self.sparse_model.embed(texts))
        
        points = []
        for i, chunk in enumerate(chunks):
            sparse_emb = sparse_embeddings[i]
            
            points.append(
                models.PointStruct(
                    id=chunk.id,
                    vector={
                        "dense": dense_embeddings[i].tolist(),
                        "sparse": models.SparseVector(
                            indices=sparse_emb.indices.tolist(),
                            values=sparse_emb.values.tolist()
                        )
                    },
                    payload={
                        "text": chunk.text,
                        **chunk.metadata
                    }
                )
            )
            
        print(f"Adding {len(chunks)} hybrid chunks to Qdrant...")
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        print("Done adding chunks.")

    def search(self, query: str, limit: int = 5):
        # Embed the query in both dense (meaning) and sparse (keywords)
        dense_query = list(self.embedding_model.embed([query]))[0].tolist()
        sparse_query = list(self.sparse_model.embed([query]))[0]
        
        # Perform Hybrid Search using Reciprocal Rank Fusion (RRF)
        results = self.client.query_points(
            collection_name=self.collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense_query,
                    using="dense",
                    limit=20
                ),
                models.Prefetch(
                    query=models.SparseVector(
                        indices=sparse_query.indices.tolist(),
                        values=sparse_query.values.tolist()
                    ),
                    using="sparse",
                    limit=60
                )
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=limit,
            with_payload=True
        )
        
        return results.points

    def delete_document(self, filename: str):
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.Filter(
                must=[
                    models.FieldCondition(
                        key="source",
                        match=models.MatchValue(value=filename)
                    )
                ]
            ),
            wait=True
        )
