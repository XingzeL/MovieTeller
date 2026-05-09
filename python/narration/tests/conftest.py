import pytest

# Two fake PNG streams (signature + junk); split_png_blob only needs signatures.
def _fake_png(body: bytes) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + body


FAKE_PNG_A = _fake_png(b"A")
FAKE_PNG_B = _fake_png(b"B")


@pytest.fixture
def fake_concat_png_stdout() -> bytes:
    return FAKE_PNG_A + FAKE_PNG_B
