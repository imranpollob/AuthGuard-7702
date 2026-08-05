"""Token-budget enforcement: chunk selection and flat downsampling never exceed max size,
and never silently truncate to a prefix when over budget (evenly-spaced selection instead)."""
import numpy as np

from features.encode import chunk_token_ids
from models.flat_cnn import downsample_to_budget


def test_chunk_token_ids_respects_max_chunks():
    ids = np.arange(1, 5000)  # way more than one chunk_size*max_chunks budget
    chunks = chunk_token_ids(ids, chunk_size=256, max_chunks=8)
    assert chunks.shape == (8, 256)


def test_chunk_token_ids_no_cap_keeps_everything():
    ids = np.arange(1, 5000)
    chunks = chunk_token_ids(ids, chunk_size=256, max_chunks=None)
    assert chunks.shape[0] == int(np.ceil(len(ids) / 256))


def test_chunk_selection_is_evenly_spaced_not_prefix():
    ids = np.arange(0, 256 * 100)  # 100 chunks worth
    chunks = chunk_token_ids(ids, chunk_size=256, max_chunks=10)
    # the last selected chunk's first token should be near the END of the stream, not chunk #9
    last_chunk_first_token = chunks[-1, 0]
    assert last_chunk_first_token > 256 * 50  # far past a prefix-truncation region


def test_flat_downsample_respects_max_len():
    ids = np.arange(1, 50000)
    out = downsample_to_budget(ids, max_len=2048)
    assert out.shape == (2048,)


def test_flat_downsample_pads_short_sequences():
    ids = np.arange(1, 100)
    out = downsample_to_budget(ids, max_len=2048)
    assert out.shape == (2048,)
    assert out[99:].sum() == 0  # padded with zeros beyond actual content
