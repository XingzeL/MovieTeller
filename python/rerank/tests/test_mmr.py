import numpy as np

from rerank import mmr_select


def test_mmr_select_prefers_diverse_second_candidate():
    query = np.asarray([1.0, 0.0], dtype=np.float32)
    candidates = np.asarray(
        [
            [0.95, 0.31],
            [0.94, 0.34],
            [0.80, -0.60],
        ],
        dtype=np.float32,
    )
    selected = mmr_select(
        query_vector=query,
        candidate_vectors=candidates,
        top_k=2,
        lambda_mult=0.7,
    )
    assert [row.index for row in selected] == [0, 2]
    assert selected[1].redundancy_score < selected[0].relevance_score


def test_mmr_select_accepts_precomputed_relevance_scores():
    query = np.asarray([1.0, 0.0], dtype=np.float32)
    candidates = np.asarray([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    selected = mmr_select(
        query_vector=query,
        candidate_vectors=candidates,
        relevance_scores=[0.9, 0.5],
        top_k=2,
        lambda_mult=0.5,
    )
    assert [row.index for row in selected] == [0, 1]


def test_mmr_select_returns_empty_for_zero_top_k():
    selected = mmr_select(
        query_vector=np.asarray([1.0, 0.0], dtype=np.float32),
        candidate_vectors=np.asarray([[1.0, 0.0]], dtype=np.float32),
        top_k=0,
    )
    assert selected == ()
