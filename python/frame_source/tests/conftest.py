import pytest


@pytest.fixture()
def fake_concat_png_stdout():
    return b"\x89PNG\r\n\x1a\nA\x89PNG\r\n\x1a\nB"
