# Copyright © 2026 Technology Matters
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see https://www.gnu.org/licenses/.

import gzip
import json
import uuid

import boto3
import pytest
import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.test import override_settings
from moto import mock_aws

from apps.shared_data.services import GeoJsonFileStorage, geojson_upload_service
from apps.storage.s3 import GZIP_COMPRESS_LEVEL

pytestmark = pytest.mark.django_db

SAMPLE_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [-0.1805502450716432, -78.48306234911033],
            },
            "properties": {"title": "sample point"},
        }
    ],
}
SAMPLE_GEOJSON_BYTES = json.dumps(SAMPLE_GEOJSON).encode("utf-8")
EMPTY_FEATURE_COLLECTION = {"type": "FeatureCollection", "features": []}


def _s3_client():
    return boto3.client("s3", region_name=settings.AWS_S3_REGION_NAME)


def _read_object(key):
    return (
        _s3_client().get_object(Bucket=settings.DATA_ENTRY_FILE_S3_BUCKET, Key=key)["Body"].read()
    )


def _head_object(key):
    return _s3_client().head_object(Bucket=settings.DATA_ENTRY_FILE_S3_BUCKET, Key=key)


def _ensure_bucket():
    """Create the S3 bucket inside the active moto mock context.

    Must run inside the test body (not in a fixture): pytest resolves
    fixtures before the mock_aws-decorated function executes, so bucket
    creation in a fixture would hit real AWS instead of moto.
    """
    bucket_name = settings.DATA_ENTRY_FILE_S3_BUCKET
    kwargs = {}
    if settings.AWS_S3_REGION_NAME != "us-east-1":
        kwargs["CreateBucketConfiguration"] = {"LocationConstraint": settings.AWS_S3_REGION_NAME}
    _s3_client().create_bucket(Bucket=bucket_name, **kwargs)


@mock_aws
def test_geojson_storage_gzips_content():
    _ensure_bucket()
    storage = GeoJsonFileStorage()
    key = "geojson/vc-1/vc-1.geojson"

    saved = storage.save(key, ContentFile(SAMPLE_GEOJSON_BYTES))

    assert saved == key
    raw = _read_object(saved)
    assert json.loads(gzip.decompress(raw)) == SAMPLE_GEOJSON


@mock_aws
def test_geojson_storage_sets_http_metadata():
    _ensure_bucket()
    storage = GeoJsonFileStorage()
    key = "geojson/vc-2/vc-2.geojson"

    storage.save(key, ContentFile(SAMPLE_GEOJSON_BYTES))

    metadata = _head_object(key)
    assert metadata["ContentEncoding"] == "gzip"
    assert metadata["ContentType"] == "application/geo+json"
    assert metadata["ContentLength"] < len(SAMPLE_GEOJSON_BYTES)


@mock_aws
def test_gzip_compression_is_level_6_and_deterministic():
    """The synchronous compression level is pinned to 6 (not gzip's default
    9: ~3x the CPU for ~0.34pp more bytes on a 50MB payload) and mtime=0
    makes identical input produce identical bytes / stable ETags."""
    _ensure_bucket()
    storage = GeoJsonFileStorage()

    assert GZIP_COMPRESS_LEVEL == 6
    first = storage._gzip_content(ContentFile(SAMPLE_GEOJSON_BYTES)).read()
    second = storage._gzip_content(ContentFile(SAMPLE_GEOJSON_BYTES)).read()

    assert first == second
    assert first == gzip.compress(SAMPLE_GEOJSON_BYTES, compresslevel=GZIP_COMPRESS_LEVEL, mtime=0)

    key = "geojson/vc-det/det.geojson"
    storage.save(key, ContentFile(SAMPLE_GEOJSON_BYTES))
    assert _read_object(key) == first


@mock_aws
def test_signed_url_serves_gzipped_body_and_metadata_over_http():
    """Wire-level check: what actually arrives at a browser. moto serves the
    presigned URL through its HTTP interception, so this proves real response
    headers and body bytes delivered over an actual HTTP request.

    What it proves / does not prove: requests auto-decodes Content-Encoding:
    gzip in .content (exactly what a browser does), so the decoded body is
    asserted to equal the original payload — requests raises
    ContentDecodingError if the wire body were not valid gzip, and
    Content-Length is asserted to be the canonical compressed byte count, so
    the wire body is pinned to the gzip bytes. moto does not validate SigV4
    signatures (it cannot reject a request), so signature expiry/authz
    semantics remain covered by the real-browser e2e run."""
    _ensure_bucket()
    key = f"geojson/vc-{uuid.uuid4().hex[:8]}/points.geojson"
    geojson_upload_service.storage.save(key, ContentFile(SAMPLE_GEOJSON_BYTES))

    signed_url = geojson_upload_service.get_signed_url(key)

    response = requests.get(signed_url, timeout=10)

    assert response.status_code == 200
    # Assert the served headers before reading .content (requests decodes the
    # body on read, like a browser would).
    assert response.headers["Content-Encoding"] == "gzip"
    assert response.headers["Content-Type"] == "application/geo+json"
    assert response.headers["Content-Length"] == str(
        len(gzip.compress(SAMPLE_GEOJSON_BYTES, compresslevel=GZIP_COMPRESS_LEVEL, mtime=0))
    )
    assert response.content == SAMPLE_GEOJSON_BYTES


@mock_aws
def test_overwrite_writes_exact_key_even_when_save_would_rename():
    _ensure_bucket()
    storage = GeoJsonFileStorage()
    key = "geojson/vc-3/vc-3.geojson"
    storage.save(key, ContentFile(json.dumps(EMPTY_FEATURE_COLLECTION).encode("utf-8")))

    with override_settings(AWS_S3_FILE_OVERWRITE=False):
        renamer = GeoJsonFileStorage()
        renamed = renamer.save(key, ContentFile(b"replacement"))
    assert renamed != key

    # The exact key still holds the original object: save() renamed the new
    # content instead of rewriting in place.
    original_bytes = _read_object(key)
    assert json.loads(gzip.decompress(original_bytes)) == EMPTY_FEATURE_COLLECTION

    returned = storage.overwrite(key, ContentFile(SAMPLE_GEOJSON_BYTES))

    assert returned == key
    raw = _read_object(key)
    assert json.loads(gzip.decompress(raw)) == SAMPLE_GEOJSON
    metadata = _head_object(key)
    assert metadata["ContentEncoding"] == "gzip"
