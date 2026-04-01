from fastapi import UploadFile, HTTPException, status
import os

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.md', '.txt', '.json', '.yaml', '.yml'}
ALLOWED_MIME_TYPES = {
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'text/markdown',
    'text/plain',
    'application/json',
    'application/x-yaml',
    'text/yaml'
}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB

async def validate_uploaded_file(file: UploadFile):
    # Check if empty
    file.file.seek(0, 2)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File cannot be empty"
        )

    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size of 25MB"
        )

    # Check extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File extension {ext} not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Check MIME type
    if file.content_type not in ALLOWED_MIME_TYPES and not file.content_type.startswith("text/"):
         # For txt, markdown, yaml, sometimes content type varies.
         # For strictly pdf and docx we enforce it more rigidly.
         if ext in ['.pdf', '.docx']:
             raise HTTPException(
                 status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                 detail=f"Invalid MIME type {file.content_type} for extension {ext}"
             )

    return True
