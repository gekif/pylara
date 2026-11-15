"""
File uploads: UploadedFile and a multipart/form-data parser (standard library only).
"""

import os
import re
import secrets
from email import policy
from email.parser import BytesParser
from typing import Dict, Tuple

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]")


class UploadedFile:
    """A file sent in a multipart form. The whole content is held in memory."""

    def __init__(self, filename: str, content: bytes, content_type: str = "application/octet-stream"):
        self.original_name = filename or ""
        self.filename = self.clean_name(filename or "")
        self.content = content
        self.content_type = content_type
        self.size = len(content)

    @staticmethod
    def clean_name(name: str) -> str:
        """Strip folders, replace unsafe characters, drop leading dots."""
        name = name.replace("\\", "/").split("/")[-1]
        return _UNSAFE.sub("_", name).lstrip(".")[:200]

    @property
    def extension(self) -> str:
        return os.path.splitext(self.filename)[1].lstrip(".").lower()

    def save(self, directory: str, name: str = None) -> str:
        """
        Write the file into `directory` and return its full path.

        Without `name` a random name is used (plus the original extension), which is the safe
        default. An existing file is never overwritten (FileExistsError).
        """
        os.makedirs(directory, exist_ok=True)
        if name is None:
            ext = self.extension
            name = secrets.token_hex(16) + (f".{ext}" if ext else "")
        else:
            name = self.clean_name(name)
            if not name:
                raise ValueError("Invalid file name.")
        path = os.path.join(directory, name)
        with open(path, "xb") as f:
            f.write(self.content)
        return path

    def __repr__(self):
        return f"<UploadedFile {self.filename!r} {self.size} bytes>"


def parse_multipart(content_type: str, body: bytes) -> Tuple[Dict[str, str], Dict[str, UploadedFile]]:
    """Return (text_fields, files) from a multipart/form-data body."""
    fields: Dict[str, str] = {}
    files: Dict[str, UploadedFile] = {}
    header = b"Content-Type: " + content_type.encode("latin-1", errors="replace") + b"\r\nMIME-Version: 1.0\r\n\r\n"
    message = BytesParser(policy=policy.HTTP).parsebytes(header + body)
    if not message.is_multipart():
        return fields, files
    for part in message.iter_parts():
        if part.get_content_disposition() != "form-data":
            continue
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        payload = part.get_payload(decode=True) or b""
        filename = part.get_filename()
        if filename is not None:
            if filename == "" and not payload:
                continue                      # an empty <input type="file">
            files[name] = UploadedFile(filename, payload, part.get_content_type())
        else:
            fields[name] = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    return fields, files
