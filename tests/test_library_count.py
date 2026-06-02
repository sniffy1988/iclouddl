from unittest.mock import MagicMock, patch

from iclouddownloader.icloud.library import count_library_photos


def test_count_iterates_album():
    album = MagicMock()
    album.__len__.return_value = 42

    def _photos():
        for i in range(3):
            yield MagicMock(id=str(i))

    album.__iter__ = lambda self: _photos()
    api = MagicMock()
    api.photos.albums.get.return_value = album

    assert count_library_photos(api) == 3


def test_count_falls_back_to_iteration_when_len_zero():
    album = MagicMock()
    album.__len__.return_value = 0

    def _photos():
        for i in range(3):
            yield MagicMock(id=str(i))

    album.__iter__ = lambda self: _photos()
    api = MagicMock()
    api.photos.albums.get.return_value = album

    with patch(
        "iclouddownloader.icloud.library.iter_library_photos",
        return_value=iter([1, 2, 3]),
    ):
        assert count_library_photos(api) == 3
