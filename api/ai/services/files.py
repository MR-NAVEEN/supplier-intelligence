import os

MAX_UPLOAD_BYTES = 50 * 1024 * 1024

PDF_EXTENSIONS = {'.pdf'}
PDF_CONTENT_TYPES = {'application/pdf', 'application/x-pdf'}

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tif', '.tiff'}
IMAGE_CONTENT_TYPES = {
    'image/jpeg',
    'image/jpg',
    'image/png',
    'image/webp',
    'image/gif',
    'image/bmp',
    'image/tiff',
}

SPREADSHEET_EXTENSIONS = {'.xlsx', '.xlsm', '.csv', '.tsv'}
SPREADSHEET_CONTENT_TYPES = {
    'text/csv',
    'text/tab-separated-values',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.ms-excel.sheet.macroenabled.12',
}
XLS_EXTENSIONS = {'.xls'}


def file_ext(upload):
    name = (getattr(upload, 'name', '') or '').lower()
    if '.' not in name:
        return ''
    return '.' + name.rsplit('.', 1)[-1]


def file_content_type(upload):
    return (getattr(upload, 'content_type', '') or '').lower()


def classify_upload(upload):
    ext = file_ext(upload)
    content_type = file_content_type(upload)
    if ext in PDF_EXTENSIONS or content_type in PDF_CONTENT_TYPES:
        return 'pdf'
    if ext in IMAGE_EXTENSIONS or content_type in IMAGE_CONTENT_TYPES:
        return 'image'
    if ext in SPREADSHEET_EXTENSIONS or content_type in SPREADSHEET_CONTENT_TYPES:
        return 'spreadsheet'
    if ext in XLS_EXTENSIONS:
        return 'xls'
    return 'unknown'


def upload_too_large(upload):
    return (getattr(upload, 'size', 0) or 0) > MAX_UPLOAD_BYTES
