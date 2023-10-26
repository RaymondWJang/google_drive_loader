import os
import io
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Define the SCOPES. If modifying these scopes, delete the token.json.
# This scope allows for full read/write access to the authenticated user's account.
SCOPES = ["https://www.googleapis.com/auth/drive"]

# The path to the service account key file.
SERVICE_ACCOUNT_FILE = "service_key.json"


def create_service():
    """Create a service object for the Google Drive API."""
    # Load the service account credentials from the key file
    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

    # Build the service object for the Google Drive API
    service = build("drive", "v3", credentials=credentials)

    return service


def list_files(service) -> list:
    all_files = []
    page_token = None

    while True:
        results = (
            service.files()
            .list(
                pageSize=1000,
                fields="nextPageToken, files(id, name, parents, mimeType)",
                pageToken=page_token,
            )
            .execute()
        )
        items = results.get("files", [])
        all_files.extend(items)
        page_token = results.get("nextPageToken", None)

        if page_token is None:
            break

    print(f"Found {len(all_files)} files.")
    # print(all_files)

    def recurse_to_the_root(item_id):
        item = next((item for item in all_files if item["id"] == item_id), None)
        if "parents" in item:
            parent_id = item["parents"][0]
            return f"{recurse_to_the_root(parent_id)}/{item['name']}"
        else:
            return item["name"]

    files = [
        item
        for item in all_files
        if item["mimeType"] != "application/vnd.google-apps.folder"
    ]

    for file in files:
        file["path"] = recurse_to_the_root(file["id"])

    return files


# def list_files(service) -> list:
#     # Call the Drive v3 API
#     results = (
#         service.files()
#         .list(
#             pageSize=1000,  # you can change the page size
#             fields="nextPageToken, files(id, name, parents, mimeType)",
#         )
#         .execute()
#     )
#     items = results.get("files", [])

#     if len(items) == 1000:
#         raise Exception(
#             "You might have more than 1000 files. You need to handle pagination."
#         )
#     else:
#         print(f"Found {len(items)} files.")

#     def recurse_to_the_root(item_id):
#         item = next((item for item in items if item["id"] == item_id), None)
#         if "parents" in item:
#             parent_id = item["parents"][0]
#             return f"{recurse_to_the_root(parent_id)}/{item['name']}"
#         else:
#             return item["name"]

#     files = [
#         item
#         for item in items
#         if item["mimeType"] != "application/vnd.google-apps.folder"
#     ]

#     for file in files:
#         file["path"] = recurse_to_the_root(file["id"])

#     # need to handle pagination here if you have more than 1000 files
#     return files


def is_folder_and_download(service, file):
    if file["mimeType"] == "application/vnd.google-apps.folder":
        print(f"Folder: {file['name']}")

        # List files in the folder
        results = (
            service.files()
            .list(
                q=f"'{file['id']}' in parents",
                fields="nextPageToken, files(id, name, mimeType)",
            )
            .execute()
        )
        items = results.get("files", [])
        if not items:
            print("No files found in the folder.")
        else:
            download_files(service, items)  # Download each file in the folder
        return True
    return False


def download_file_kernel(service, file):
    # for file in files:
    print(f"File: {file['name']}, MIME Type: {file['mimeType']}")
    if is_folder_and_download(service, file):
        raise Exception("Folder found among files.")

    # Check the file's MIME type. If it's a Google Doc, Sheet, Slide, etc.,
    # we need to export it. Otherwise, we can just download it directly.
    if file["mimeType"] == "application/vnd.google-apps.document":
        request = service.files().export_media(
            fileId=file["id"],
            mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        filename = file["name"] + ".docx"
    elif file["mimeType"] == "application/vnd.google-apps.spreadsheet":
        request = service.files().export_media(
            fileId=file["id"],
            mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        filename = file["name"] + ".xlsx"
    elif file["mimeType"] == "application/vnd.google-apps.presentation":
        request = service.files().export_media(
            fileId=file["id"],
            mimeType="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        )
        filename = file["name"] + ".pptx"
    else:
        request = service.files().get_media(fileId=file["id"])
        filename = file["name"]

    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while done is False:
        status, done = downloader.next_chunk()
        print(f"Download {int(status.progress() * 100)}%")

    # Create the directory if it doesn't exist
    os.makedirs(Path(file["path"]).parent, exist_ok=True)

    # The file's content is stored in fh (a BytesIO object)
    with io.open(Path(file["path"]).parent / filename, "wb") as f:
        fh.seek(0)
        f.write(fh.read())


def download_files(service, files):
    # It's generally recommended to be set to the number of processors on the machine, times 5
    # with ThreadPoolExecutor(max_workers=os.cpu_count() / 4) as executor:
    #     executor.map(lambda file: download_file_kernel(service, file), files)
    for file in files:
        download_file_kernel(service, file)


def main():
    start = datetime.now()
    service = create_service()
    files = list_files(service)

    if not files:
        print("No files found.")
    else:
        print("Files:")
        for item in files:
            print("{0} ({1})".format(item["name"], item["id"]))

        download_files(service, files)

    print(f"Time taken: {(datetime.now() - start)}")
    print("All downloads complete!")


if __name__ == "__main__":
    main()
