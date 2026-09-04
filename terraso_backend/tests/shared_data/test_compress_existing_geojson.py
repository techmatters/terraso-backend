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
import io
import json
import uuid

import boto3
import pytest
from django.conf import settings
from django.core.management import call_command
from mixer.backend.django import mixer
from moto import mock_aws

from apps.shared_data.models import DataEntry, VisualizationConfig
from apps.shared_data.services import GEOJSON_CONTENT_TYPE, geojson_upload_service
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


def _s3_client():
    return boto3.client("s3", region_name=settings.AWS_S3_REGION_NAME)


def _bucket_name():
    return settings.DATA_ENTRY_FILE_S3_BUCKET


def _head_object(key):
    return _s3_client().head_object(Bucket=_bucket_name(), Key=key)


def _read_object(key):
    return _s3_client().get_object(Bucket=_bucket_name(), Key=key)["Body"].read()


def _ensure_bucket():
    """Create the S3 bucket inside the active moto mock context.

    Must run inside the test body (not in a fixture): pytest resolves
    fixtures before the mock_aws-decorated function executes, so bucket
    creation in a fixture would hit real AWS instead of moto.
    """
    kwargs = {}
    if settings.AWS_S3_REGION_NAME != "us-east-1":
        kwargs["CreateBucketConfiguration"] = {"LocationConstraint": settings.AWS_S3_REGION_NAME}
    _s3_client().create_bucket(Bucket=_bucket_name(), **kwargs)


def _put_plain_object(key, body, content_type="application/geo+json", extra=None):
    """Store a pre-compression object: plain bytes, no Content-Encoding."""
    kwargs = {"Bucket": _bucket_name(), "Key": key, "Body": body}
    if content_type is not None:
        kwargs["ContentType"] = content_type
    if extra:
        kwargs.update(extra)
    _s3_client().put_object(**kwargs)


def _gzip_bytes(data):
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb") as gz:
        gz.write(data)
    return buffer.getvalue()


def _run_command(*args, **kwargs):
    output = io.StringIO()
    call_command("compress_existing_geojson", *args, stdout=output, **kwargs)
    return output


def _generated_key():
    return f"geojson/vc-{uuid.uuid4().hex[:8]}/layer.geojson"


def _make_visualization_config(key):
    return mixer.blend(
        VisualizationConfig,
        size=1,
        geojson_s3_key=key,
        data_entry=mixer.blend(DataEntry, url="https://example.com/unused/file.csv"),
    )


@mock_aws
def test_generated_geojson_object_is_compressed_in_place():
    """Headline: a plain generated GeoJSON object referenced by a
    VisualizationConfig.geojson_s3_key becomes gzip-encoded at the same key,
    with correct HTTP metadata, and gunzips to byte-identical content."""
    _ensure_bucket()
    key = _generated_key()
    _put_plain_object(key, SAMPLE_GEOJSON_BYTES)
    _make_visualization_config(key)

    output = _run_command()

    metadata = _head_object(key)
    assert metadata["ContentEncoding"] == "gzip"
    assert metadata["ContentType"] == GEOJSON_CONTENT_TYPE
    assert metadata["ContentLength"] < len(SAMPLE_GEOJSON_BYTES)

    raw = _read_object(key)
    assert gzip.decompress(raw) == SAMPLE_GEOJSON_BYTES

    # No renamed copies: the exact key is the only object in the bucket.
    keys = [obj["Key"] for obj in _s3_client().list_objects_v2(Bucket=_bucket_name())["Contents"]]
    assert keys == [key]

    assert "Scanned: 1" in output.getvalue()
    assert "Compressed: 1" in output.getvalue()
    assert "0.0% reduction" not in output.getvalue()


@mock_aws
def test_second_run_is_idempotent():
    _ensure_bucket()
    key = _generated_key()
    _put_plain_object(key, SAMPLE_GEOJSON_BYTES)
    _make_visualization_config(key)

    _run_command()
    after_first = _head_object(key)
    first_bytes = _read_object(key)

    output = _run_command()

    assert "Compressed: 0" in output.getvalue()
    assert "Already compressed: 1" in output.getvalue()

    after_second = _head_object(key)
    assert after_second["ContentEncoding"] == "gzip"
    assert after_second["ETag"] == after_first["ETag"]
    assert after_second["ContentLength"] == after_first["ContentLength"]
    assert _read_object(key) == first_bytes


@mock_aws
def test_dry_run_writes_nothing_but_reports_the_same_plan():
    _ensure_bucket()
    key = _generated_key()
    _put_plain_object(key, SAMPLE_GEOJSON_BYTES)
    _make_visualization_config(key)

    output = _run_command("--dry-run")

    assert "Would compress: 1" in output.getvalue()
    assert "Compressed: 1" not in output.getvalue()
    assert "dry" in output.getvalue().lower()

    # Nothing was written: still plain, no metadata, same ETag.
    metadata = _head_object(key)
    assert "ContentEncoding" not in metadata
    assert metadata["ContentLength"] == len(SAMPLE_GEOJSON_BYTES)
    assert _read_object(key) == SAMPLE_GEOJSON_BYTES
    assert len(_s3_client().list_objects_v2(Bucket=_bucket_name())["Contents"]) == 1


@mock_aws
def test_missing_and_invalid_objects_are_skipped_and_run_continues():
    """Also pins the consequence of the header-only idempotency check: an
    object whose body is gzip but whose Content-Encoding does not say so is no
    longer decoded-and-repaired. That state is not producible by any code here,
    so the command just declines to touch it (invalid, bytes untouched) instead
    of downloading and sniffing every body to defend against it."""
    _ensure_bucket()
    good_key = _generated_key()
    _put_plain_object(good_key, SAMPLE_GEOJSON_BYTES)
    _make_visualization_config(good_key)

    missing_key = _generated_key()
    _make_visualization_config(missing_key)  # no object in S3

    invalid_plain_key = _generated_key()
    _put_plain_object(invalid_plain_key, b"this is not json at all \x00\x01")
    _make_visualization_config(invalid_plain_key)

    gzip_body_without_header_key = _generated_key()
    gzip_body = _gzip_bytes(b"not json either")  # fixed bytes: GzipFile stamps mtime
    _put_plain_object(gzip_body_without_header_key, gzip_body)
    _make_visualization_config(gzip_body_without_header_key)

    output = _run_command()

    text = output.getvalue()
    assert "Compressed: 1" in text
    assert "Missing: 1" in text
    assert "Invalid: 2" in text
    assert "Failed: 0" in text
    assert missing_key in text
    assert invalid_plain_key in text
    assert gzip_body_without_header_key in text

    # Skipped means untouched: not rewritten, not given a gzip header.
    assert _read_object(gzip_body_without_header_key) == gzip_body
    assert "ContentEncoding" not in _head_object(gzip_body_without_header_key)
    assert _read_object(invalid_plain_key) == b"this is not json at all \x00\x01"


@mock_aws
def test_backfilled_object_serves_gunzipable_bytes_and_signed_url():
    """After the backfill, the object under the unchanged key is a gzip body
    that gunzips to the original GeoJSON — which is exactly what the browser /
    mapbox-gl client decoding Content-Encoding receives — and the signed-URL
    generator still points at the same key. The backend never byte-reads
    these objects, so the client-side decode is simulated here."""
    _ensure_bucket()
    key = _generated_key()
    vc = _make_visualization_config(key)
    _put_plain_object(key, SAMPLE_GEOJSON_BYTES)

    _run_command()

    raw = _read_object(vc.geojson_s3_key)
    assert json.loads(gzip.decompress(raw)) == SAMPLE_GEOJSON
    assert vc.geojson_s3_key in geojson_upload_service.get_signed_url(vc.geojson_s3_key)


@mock_aws
def test_object_is_compressed_exactly_once_with_canonical_bytes():
    """The stored object must be exactly one gzip pass over the original
    plaintext with the canonical write-path settings (level 6, mtime=0): a
    second compression pass would change the bytes, waste CPU and break the
    byte-identical rewrite guarantee."""
    _ensure_bucket()
    view = SAMPLE_GEOJSON_BYTES
    key = _generated_key()
    _put_plain_object(key, view)
    _make_visualization_config(key)

    _run_command()

    stored = _read_object(key)
    assert stored == gzip.compress(view, compresslevel=GZIP_COMPRESS_LEVEL, mtime=0)
    assert gzip.decompress(stored) == view


@mock_aws
def test_content_type_is_canonicalized_on_backfill():
    """One canonical rule for both write paths: every generated layer object
    is served as application/geo+json, whatever Content-Type it was stored
    with (or none). Preserving the old value created a fresh-write vs
    backfilled divergence and forced a shared-singleton override race in
    overwrite()."""
    _ensure_bucket()
    # A generated object that an older writer stored as application/json.
    json_type_key = f"geojson/vc-{uuid.uuid4().hex[:8]}/layer.json"
    _put_plain_object(json_type_key, b'{"a": 1}', content_type="application/json")
    _make_visualization_config(json_type_key)
    # Old generated object stored without any Content-Type (S3 stores a default).
    no_type_key = _generated_key()
    _put_plain_object(no_type_key, SAMPLE_GEOJSON_BYTES, content_type=None)
    _make_visualization_config(no_type_key)

    _run_command()

    json_metadata = _head_object(json_type_key)
    assert json_metadata["ContentEncoding"] == "gzip"
    assert json_metadata["ContentType"] == GEOJSON_CONTENT_TYPE
    assert gzip.decompress(_read_object(json_type_key)) == b'{"a": 1}'

    no_type_metadata = _head_object(no_type_key)
    assert no_type_metadata["ContentEncoding"] == "gzip"
    assert no_type_metadata["ContentType"] == GEOJSON_CONTENT_TYPE
