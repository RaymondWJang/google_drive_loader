import pytest
from unittest.mock import Mock, patch
from main import create_service, list_files, download_file_kernel


def test_create_service(mocker):
    # Mock the 'from_service_account_file' method
    mock_from_service_account_file = mocker.patch(
        "main.service_account.Credentials.from_service_account_file",
        return_value=Mock(),
    )

    # Mock the 'build' function
    mock_build = mocker.patch("main.build", return_value=Mock())

    service = create_service()

    # Assert that the expected methods were called with the correct parameters
    mock_from_service_account_file.assert_called_once_with(
        "service_key.json",
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    mock_build.assert_called_once_with(
        "drive", "v3", credentials=mock_from_service_account_file.return_value
    )
    assert service == mock_build.return_value


@pytest.fixture
def mock_service():
    """Fixture that creates a mock service object for Google Drive API."""
    # Create a mock service object with a mock files().list().execute() chain
    mock_service = Mock()
    mock_service.files().list().execute.return_value = {
        "files": [
            {
                "id": "1",
                "name": "File1",
                "mimeType": "application/pdf",
                "parents": ["0"],
            },
            # Add more mock files if necessary
        ]
    }
    mock_service.files().export_media().execute.return_value = b"some file content"
    mock_service.files().get_media().execute.return_value = b"some file content"
    return mock_service


def test_list_files_retrieves_files(mock_service):
    """Test if list_files retrieves files correctly."""
    files = list_files(mock_service)

    assert len(files) == 1  # or however many mock files you added
    assert files[0]["name"] == "File1"  # check that the file data is correct


def test_list_files_handles_max_files(mock_service):
    """Test how list_files handles having exactly 1000 files."""
    # Modify the return value to simulate having 1000 files
    mock_service.files().list().execute.return_value = {
        "files": [
            {"id": str(i), "name": f"File{i}", "mimeType": "application/pdf"}
            for i in range(1000)
        ]
    }

    with pytest.raises(Exception) as exc_info:
        list_files(mock_service)

    assert "You might have more than 1000 files." in str(exc_info.value)


def test_recurse_to_the_root(mock_service):
    """Test the functionality of the internal recurse_to_the_root function."""
    # This is a bit more complex because recurse_to_the_root is an internal function.
    # might want to refactor code to make this function independent and more testable.

    mock_service.files().list().execute.return_value = {
        "files": [
            {
                "id": "1",
                "name": "Child",
                "parents": ["0"],
                "mimeType": "application/pdf",
            },
            {
                "id": "0",
                "name": "Parent",
                "mimeType": "application/vnd.google-apps.folder",
            },
        ]
    }

    files = list_files(mock_service)

    assert len(files) == 1
    assert files[0]["path"] == "Parent/Child"  # Check if the path is computed correctly


# This fixture will be used to simulate the file system
@pytest.fixture
def mock_filesystem():
    with patch("io.open", new_callable=Mock) as mock_open:
        with patch("os.makedirs", new_callable=Mock) as mock_makedirs:
            yield mock_open, mock_makedirs


def test_download_document(mock_service, mock_filesystem):
    mock_open, mock_makedirs = mock_filesystem
    file = {
        "id": "1",
        "name": "TestDoc",
        "mimeType": "application/vnd.google-apps.document",
        "path": "/path/to",
    }

    with patch(
        "googleapiclient.http.MediaIoBaseDownload", autospec=True
    ) as mock_download:
        mock_download.return_value.next_chunk.return_value = (
            Mock(progress=lambda: 1),
            True,
        )
        download_file_kernel(mock_service, file)

    mock_open.assert_called_once()
    mock_makedirs.assert_called_once_with("/path/to", exist_ok=True)


def test_download_spreadsheet(mock_service, mock_filesystem):
    mock_open, mock_makedirs = mock_filesystem
    file = {
        "id": "1",
        "name": "TestDoc",
        "mimeType": "application/vnd.google-apps.spreadsheet",
        "path": "/path/to",
    }

    with patch(
        "googleapiclient.http.MediaIoBaseDownload", autospec=True
    ) as mock_download:
        mock_download.return_value.next_chunk.return_value = (
            Mock(progress=lambda: 1),
            True,
        )
        download_file_kernel(mock_service, file)

    mock_open.assert_called_once()
    mock_makedirs.assert_called_once_with("/path/to", exist_ok=True)


def test_download_presentation(mock_service, mock_filesystem):
    mock_open, mock_makedirs = mock_filesystem
    file = {
        "id": "1",
        "name": "TestDoc",
        "mimeType": "application/vnd.google-apps.presentation",
        "path": "/path/to",
    }

    with patch(
        "googleapiclient.http.MediaIoBaseDownload", autospec=True
    ) as mock_download:
        mock_download.return_value.next_chunk.return_value = (
            Mock(progress=lambda: 1),
            True,
        )
        download_file_kernel(mock_service, file)

    mock_open.assert_called_once()
    mock_makedirs.assert_called_once_with("/path/to", exist_ok=True)


def test_download_other_file_type(mock_service, mock_filesystem):
    mock_open, mock_makedirs = mock_filesystem
    file = {
        "id": "1",
        "name": "TestDoc",
        "mimeType": "unknown_mimeType",
        "path": "/path/to",
    }

    with patch(
        "googleapiclient.http.MediaIoBaseDownload", autospec=True
    ) as mock_download:
        mock_download.return_value.next_chunk.return_value = (
            Mock(progress=lambda: 1),
            True,
        )
        download_file_kernel(mock_service, file)

    mock_open.assert_called_once()
    mock_makedirs.assert_called_once_with("/path/to", exist_ok=True)


def test_handle_folder(mock_service):
    file = {
        "id": "1",
        "name": "TestFolder",
        "mimeType": "application/vnd.google-apps.folder",
        "path": "/path/to",
    }
    with pytest.raises(Exception, match="Folder found among files."):
        download_file_kernel(mock_service, file)
