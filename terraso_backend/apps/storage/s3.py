from django.conf import settings
from storages.backends.s3boto3 import S3Boto3Storage


class ProfileImageStorage(S3Boto3Storage):
    bucket_name = settings.PROFILE_IMAGES_S3_BUCKET
