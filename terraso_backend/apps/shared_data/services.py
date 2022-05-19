from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage

from apps.storage.services import UploadService


class DataEntryFileStorage(S3Boto3Storage):
    bucket_name = settings.DATA_ENTRY_FILE_S3_BUCKET


class DataEntryUploadService(UploadService):
    storage = DataEntryFileStorage()
    base_url = settings.DATA_ENTRY_FILE_BASE_URL


data_entry_upload_service = DataEntryUploadService()
