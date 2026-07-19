import pytest
from app.services.embedding_service import embedding_service

def cosine_similarity(v1, v2):
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_v1 = sum(a * a for a in v1) ** 0.5
    norm_v2 = sum(a * a for a in v2) ** 0.5
    if norm_v1 == 0 or norm_v2 == 0:
        return 0.0
    return dot_product / (norm_v1 * norm_v2)

@pytest.mark.sanity
def test_embedding_semantic_discriminator():
    """
    Sanity test that runs embedding generation directly on real configured provider
    (local model or OpenAI API depending on environment setup) to verify semantic mapping space.
    """
    text_base = "The cat sat on the mat"
    text_similar = "A cat was sitting on a mat"
    text_unrelated = "Stock markets crashed today"

    # Call real embedding generation service
    embeddings = embedding_service.generate_embeddings([text_base, text_similar, text_unrelated])
    
    assert len(embeddings) == 3
    emb_base = embeddings[0]
    emb_similar = embeddings[1]
    emb_unrelated = embeddings[2]
    
    # Assert correct embedding shapes / sizes
    assert isinstance(emb_base, list)
    assert len(emb_base) > 0
    
    # Calculate similarities
    sim_similar = cosine_similarity(emb_base, emb_similar)
    sim_unrelated = cosine_similarity(emb_base, emb_unrelated)
    
    print(f"\nEmbedding model checked: '{embedding_service.get_embedding_model_info()}'")
    print(f"Similarity (related): {sim_similar:.4f}")
    print(f"Similarity (unrelated): {sim_unrelated:.4f}")
    
    # Assertions
    assert sim_similar > 0.7, f"Expected similarity to be > 0.7, got {sim_similar}"
    assert sim_unrelated < sim_similar, f"Expected unrelated similarity ({sim_unrelated}) to be lower than related similarity ({sim_similar})"
