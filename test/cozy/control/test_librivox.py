from unittest.mock import MagicMock
import pytest

from cozy.control.librivox import LibriVox, LibriVoxError


@pytest.fixture
def librivox_client():
    return LibriVox()


def test_search_audiobooks_success(mocker, librivox_client):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "books": [
            {"id": "1", "title": "Pride and Prejudice", "authors": [{"first_name": "Jane", "last_name": "Austen"}]}
        ]
    }
    mock_response.raise_for_status.return_value = None
    mocker.patch.object(librivox_client._session, "get", return_value=mock_response)

    results = librivox_client.search_audiobooks(query="Pride")
    assert len(results) == 1
    assert results[0]["title"] == "Pride and Prejudice"


def test_search_audiobooks_error(mocker, librivox_client):
    mocker.patch.object(librivox_client._session, "get", side_effect=Exception("Network error"))

    with pytest.raises(LibriVoxError):
        librivox_client.search_audiobooks(query="Pride")
