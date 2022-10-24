from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class S3BackupStorage(S3Boto3Storage):
    bucket_name = settings.BACKUP_S3_BUCKET
