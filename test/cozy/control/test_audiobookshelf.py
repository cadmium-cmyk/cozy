from unittest.mock import MagicMock

import pytest
import requests

from cozy.control.audiobookshelf import (
    Audiobookshelf,
    AudiobookshelfAuthError,
    AudiobookshelfConnectionError,
    AudiobookshelfError,
)


@pytest.fixture
def abs_client():
    return Audiobookshelf(host="http://abs.example.com", token="test-token")


def test_host_normalization():
    client = Audiobookshelf(host="abs.example.com:13378/")
    assert client.host == "http://abs.example.com:13378"

    client.host = "https://audiobookshelf.server.local/base/"
    assert client.host == "https://audiobookshelf.server.local/base"

    client.host = ""
    assert client.host == ""


def test_login_success(mocker, abs_client):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.content = b'{"user": {"username": "admin", "token": "secret-token"}}'
    mock_response.json.return_value = {"user": {"username": "admin", "token": "secret-token"}}

    mocker.patch.object(abs_client._session, "request", return_value=mock_response)

    user_data = abs_client.login("admin", "password123")
    assert user_data["username"] == "admin"
    assert abs_client.token == "secret-token"
    assert abs_client.is_authenticated


def test_login_missing_token(mocker, abs_client):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.content = b'{"user": {"username": "admin"}}'
    mock_response.json.return_value = {"user": {"username": "admin"}}

    mocker.patch.object(abs_client._session, "request", return_value=mock_response)

    with pytest.raises(AudiobookshelfAuthError, match="missing access token"):
        abs_client.login("admin", "password123")


def test_login_invalid_credentials(mocker, abs_client):
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    mocker.patch.object(abs_client._session, "request", return_value=mock_response)

    with pytest.raises(AudiobookshelfAuthError):
        abs_client.login("admin", "wrongpassword")


def test_ping_authenticated(mocker, abs_client):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.content = b'{"user": {"id": "user1"}}'
    mock_response.json.return_value = {"user": {"id": "user1"}}

    mocker.patch.object(abs_client._session, "request", return_value=mock_response)

    assert abs_client.ping() is True


def test_ping_unauthenticated(mocker):
    client = Audiobookshelf(host="http://abs.example.com", token=None)

    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.content = b'{"success": true}'
    mock_response.json.return_value = {"success": True}

    mocker.patch.object(client._session, "request", return_value=mock_response)

    assert client.ping() is True


def test_get_libraries(mocker, abs_client):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.content = b'{"libraries": [{"id": "lib-1", "name": "Audiobooks"}]}'
    mock_response.json.return_value = {"libraries": [{"id": "lib-1", "name": "Audiobooks"}]}

    mocker.patch.object(abs_client._session, "request", return_value=mock_response)

    libraries = abs_client.get_libraries()
    assert len(libraries) == 1
    assert libraries[0]["id"] == "lib-1"


def test_get_library_items(mocker, abs_client):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.content = (
        b'{"results": [{"id": "item-1", "media": {"metadata": {"title": "Test Book"}}}]}'
    )
    mock_response.json.return_value = {
        "results": [{"id": "item-1", "media": {"metadata": {"title": "Test Book"}}}]
    }

    mock_request = mocker.patch.object(abs_client._session, "request", return_value=mock_response)

    items = abs_client.get_library_items("lib-1", limit=10, page=1)
    assert len(items) == 1
    assert items[0]["id"] == "item-1"

    mock_request.assert_called_once()
    _, kwargs = mock_request.call_args
    assert kwargs["params"] == {"limit": 10, "page": 1}


def test_get_item(mocker, abs_client):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.content = b'{"id": "item-123", "media": {"duration": 3600}}'
    mock_response.json.return_value = {"id": "item-123", "media": {"duration": 3600}}

    mocker.patch.object(abs_client._session, "request", return_value=mock_response)

    item = abs_client.get_item("item-123")
    assert item["id"] == "item-123"
    assert item["media"]["duration"] == 3600


def test_sync_progress(mocker, abs_client):
    mock_response = MagicMock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.content = b'{"success": true}'
    mock_response.json.return_value = {"success": True}

    mock_request = mocker.patch.object(abs_client._session, "request", return_value=mock_response)

    res = abs_client.sync_progress(
        item_id="item-1", current_time=150.0, duration=300.0, is_finished=False
    )
    assert res == {"success": True}

    _, kwargs = mock_request.call_args
    assert kwargs["json"] == {
        "currentTime": 150.0,
        "duration": 300.0,
        "progress": 0.5,
        "isFinished": False,
    }


def test_get_cover_and_audio_urls(abs_client):
    cover_url = abs_client.get_cover_url("item-123")
    assert cover_url == "http://abs.example.com/api/items/item-123/cover?token=test-token"

    audio_url = abs_client.get_audio_file_url("item-123", "file-456")
    assert audio_url == "http://abs.example.com/api/items/item-123/file/file-456?token=test-token"

    unauth_client = Audiobookshelf(host="http://abs.example.com")
    assert (
        unauth_client.get_cover_url("item-123") == "http://abs.example.com/api/items/item-123/cover"
    )


def test_connection_error(mocker, abs_client):
    mocker.patch.object(
        abs_client._session, "request", side_effect=requests.RequestException("Connection refused")
    )

    with pytest.raises(AudiobookshelfConnectionError, match="Connection failed"):
        abs_client.get_libraries()


def test_http_error_handling(mocker, abs_client):
    mock_response = MagicMock()
    mock_response.ok = False
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    mocker.patch.object(abs_client._session, "request", return_value=mock_response)

    with pytest.raises(AudiobookshelfError, match="status code 500"):
        abs_client.get_libraries()
