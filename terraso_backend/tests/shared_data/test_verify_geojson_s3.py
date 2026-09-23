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

"""Tests for the verify_geojson_s3 management command."""

import gzip
import io
import json
import uuid
from io import StringIO
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core.management import CommandError, call_command

from apps.shared_data.models import DataEntry, VisualizationConfig

pytestmark = pytest.mark.django_db

CONFIG = {
    "datasetConfig": {"longitude": "lng", "latitude": "lat"},
    "annotateConfig": {"dataPoints": [{"label": "Name", "column": "name"}]},
}
CSV_CONTENT = "name,lng,lat\nsite,-77.95,-1.65\n"
GENERATED_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-77.95, -1.65]},
            "properties": {"title": None, "fields": '[{"label": "Name", "value": "site"}]'},
        }
    ],
}

STORED_DIFFERENT_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0.0, 0.0]},
            "properties": {"title": None, "fields": "[]"},
        }
    ],
}


def bytes_io(text):
    return io.BytesIO(text.encode("utf-8"))


def set_config(visualization_config, geojson_s3_key=None):
    visualization_config.configuration = CONFIG
    visualization_config.geojson_s3_key = geojson_s3_key
    visualization_config.save()


def run_command(**options):
    out = StringIO()
    call_command("verify_geojson_s3", stdout=out, **options)
    return out.getvalue()


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_matching_s3_object_reports_match(mock_source, mock_stored, visualization_config):
    """Stored S3 object identical to regenerated geojson -> MATCH."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = bytes_io(json.dumps(GENERATED_GEOJSON))

    output = run_command()

    assert "MATCH" in output
    assert "identical to S3" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_differing_s3_object_flagged_with_diff(mock_source, mock_stored, visualization_config):
    """Stored object that no longer matches generation -> DIFF with details."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = bytes_io(json.dumps(STORED_DIFFERENT_GEOJSON))

    output = run_command()

    assert "DIFF" in output
    assert "stored 1 vs generated 1 features" in output
    assert "first differing feature 0: geometry" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_no_s3_key_with_successful_generation_reports_generates(
    mock_source, mock_stored, visualization_config
):
    """Nothing on S3: the command reports whether generation succeeds."""
    set_config(visualization_config)
    mock_source.return_value = bytes_io(CSV_CONTENT)

    output = run_command()

    assert "GENERATES" in output
    assert "1 features" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_generation_returning_none_reports_no_geojson(
    mock_source, mock_stored, visualization_config
):
    """Unresolvable columns (prod 'latitude: ""' case) -> NO_GEOJSON."""
    visualization_config.configuration = {
        "datasetConfig": {"longitude": "lng", "latitude": ""},
        "annotateConfig": {"dataPoints": []},
    }
    visualization_config.save()
    mock_source.return_value = bytes_io(CSV_CONTENT)

    output = run_command()

    assert "NO_GEOJSON" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_stale_s3_key_when_generation_yields_nothing(
    mock_source, mock_stored, visualization_config
):
    """Key set on S3 but the pipeline no longer produces geojson -> STALE."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    visualization_config.configuration = {
        "datasetConfig": {"longitude": "lng", "latitude": ""},
        "annotateConfig": {"dataPoints": []},
    }
    visualization_config.save()
    mock_source.return_value = bytes_io(CSV_CONTENT)

    output = run_command()

    assert "STALE" in output
    assert "generation yields nothing" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_gzipped_s3_object_reports_match(mock_source, mock_stored, visualization_config):
    """Objects written by GzipStorageMixin (compressed) compare equal too."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = io.BytesIO(gzip.compress(json.dumps(GENERATED_GEOJSON).encode()))

    output = run_command()

    assert "MATCH" in output
    assert "identical to S3" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_corrupt_gzip_object_is_unreadable(mock_source, mock_stored, visualization_config):
    """Gzip magic followed by garbage -> UNREADABLE, not a crash."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = io.BytesIO(b"\x1f\x8b not really gzip")

    output = run_command()

    assert "UNREADABLE" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_generation_error_is_flagged_not_raised(mock_source, mock_stored, visualization_config):
    """A failing generation (e.g. missing source file) becomes GENERATION_ERROR."""
    set_config(visualization_config, geojson_s3_key=None)
    mock_source.side_effect = FileNotFoundError("File does not exist: x/test_data.csv")

    output = run_command()

    assert "GENERATION_ERROR" in output
    assert "FileNotFoundError" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_unreadable_s3_object_is_flagged(mock_source, mock_stored, visualization_config):
    """A missing/corrupt S3 object becomes UNREADABLE, not a crash."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.side_effect = FileNotFoundError("The specified key does not exist.")

    output = run_command()

    assert "UNREADABLE" in output


TUPLE_COORDS_GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": (-77.95, -1.65)},
            "properties": {"title": None, "fields": '[{"label": "Name", "value": "site"}]'},
        }
    ],
}


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_tuple_vs_list_coordinates_compare_equal(mock_source, mock_stored, visualization_config):
    """Shapely mapping() tuples vs JSON list coordinates must count as MATCH."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = bytes_io(json.dumps(GENERATED_GEOJSON))

    with patch(
        "apps.shared_data.management.commands.verify_geojson_s3.get_geojson_from_data_entry",
        return_value=TUPLE_COORDS_GEOJSON,
    ) as mock_generate:
        output = run_command()

    mock_generate.assert_called_once()
    assert "MATCH" in output
    assert "identical to S3" in output
    assert "DIFF" not in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_list_vs_tuple_coordinates_compare_equal(mock_source, mock_stored, visualization_config):
    """Shapely tuple coordinates are list-normalized before storage round-trip."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = bytes_io(json.dumps(TUPLE_COORDS_GEOJSON))

    with patch(
        "apps.shared_data.management.commands.verify_geojson_s3.get_geojson_from_data_entry",
        return_value=GENERATED_GEOJSON,
    ):
        output = run_command()

    assert "MATCH" in output
    assert "identical to S3" in output
    assert "DIFF" not in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_tuple_vs_list_coordinates_flagged_with_diff(
    mock_source, mock_stored, visualization_config
):
    """Legitimate coordinate diffs are still reported after normalization."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = bytes_io(json.dumps(GENERATED_GEOJSON))

    with patch(
        "apps.shared_data.management.commands.verify_geojson_s3.get_geojson_from_data_entry",
        return_value=STORED_DIFFERENT_GEOJSON,
    ):
        output = run_command()

    assert "DIFF" in output
    assert "first differing feature 0: geometry" in output


REPAIRED_KEY = "geojson/new/xyz.geojson"


@patch("apps.shared_data.management.commands.verify_geojson_s3.upload_geojson_to_s3")
@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_repair_bare_repairs_diff_vc(mock_source, mock_stored, mock_repair, visualization_config):
    """Bare --repair regenerates S3 geojson for a DIFF status."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = bytes_io(json.dumps(STORED_DIFFERENT_GEOJSON))
    mock_repair.return_value = REPAIRED_KEY

    output = run_command(repair="")

    mock_repair.assert_called_once_with(visualization_config.id)
    assert "DIFF" in output
    assert f"REPAIRED -> {REPAIRED_KEY}" in output


@patch("apps.shared_data.management.commands.verify_geojson_s3.upload_geojson_to_s3")
@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_repair_bare_does_not_touch_match_vc(
    mock_source, mock_stored, mock_repair, visualization_config
):
    """Bare --repair must not regenerate a VC whose status is MATCH."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = bytes_io(json.dumps(GENERATED_GEOJSON))

    output = run_command(repair="")

    mock_repair.assert_not_called()
    assert "REPAIRED" not in output
    assert "MATCH" in output


@patch("apps.shared_data.management.commands.verify_geojson_s3.upload_geojson_to_s3")
@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_repair_bare_repairs_generates_vc(
    mock_source, mock_stored, mock_repair, visualization_config
):
    """GENERATES (nothing on S3 yet) is repairable with bare --repair."""
    set_config(visualization_config)
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_repair.return_value = REPAIRED_KEY

    output = run_command(repair="")

    mock_repair.assert_called_once_with(visualization_config.id)
    assert f"REPAIRED -> {REPAIRED_KEY}" in output


@patch("apps.shared_data.management.commands.verify_geojson_s3.upload_geojson_to_s3")
@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_repair_bare_repairs_unreadable_vc(
    mock_source, mock_stored, mock_repair, visualization_config
):
    """UNREADABLE (missing/corrupt S3 object) is repairable with bare --repair."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.side_effect = FileNotFoundError("The specified key does not exist.")
    mock_repair.return_value = REPAIRED_KEY

    output = run_command(repair="")

    mock_repair.assert_called_once_with(visualization_config.id)
    assert f"REPAIRED -> {REPAIRED_KEY}" in output


@patch("apps.shared_data.management.commands.verify_geojson_s3.upload_geojson_to_s3")
@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_repair_filtered_skips_status_not_in_repair_set(
    mock_source, mock_stored, mock_repair, visualization_config
):
    """--repair=DIFF must not touch a GENERATES VC (status filter applies)."""
    set_config(visualization_config)
    mock_source.return_value = bytes_io(CSV_CONTENT)

    output = run_command(repair="DIFF")

    mock_repair.assert_not_called()
    assert "REPAIRED" not in output
    assert "GENERATES" in output


@patch("apps.shared_data.management.commands.verify_geojson_s3.upload_geojson_to_s3")
@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_repair_filtered_repairs_requested_status(
    mock_source, mock_stored, mock_repair, visualization_config
):
    """--repair=GENERATES repairs a GENERATES VC (explicit status opt-in)."""
    set_config(visualization_config)
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_repair.return_value = REPAIRED_KEY

    output = run_command(repair="GENERATES")

    mock_repair.assert_called_once_with(visualization_config.id)
    assert f"REPAIRED -> {REPAIRED_KEY}" in output


def test_repair_valid_but_non_repairable_status_is_accepted_and_skipped():
    """--repair=STALE is valid but never triggers a repair; warning is printed."""
    output = run_command(repair="STALE")

    assert "STALE is not repairable" in output
    assert "REPAIRED" not in output


def test_repair_with_unknown_status_name_raises_command_error():
    """Status names are validated against STATUSES to catch typos."""
    with pytest.raises(CommandError) as excinfo:
        run_command(repair="BOGUS")

    assert "BOGUS" in str(excinfo.value)
    assert "MATCH" in str(excinfo.value)


@patch("apps.shared_data.management.commands.verify_geojson_s3.upload_geojson_to_s3")
@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_repair_failure_is_reported_and_run_continues(
    mock_source, mock_stored, mock_repair, visualization_config
):
    """A failed repair (None return or raised error) never aborts the run."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = bytes_io(json.dumps(STORED_DIFFERENT_GEOJSON))
    mock_repair.return_value = None

    output = run_command(repair="")

    assert "REPAIR_FAILED" in output
    assert "Summary" in output


@patch("apps.shared_data.management.commands.verify_geojson_s3.upload_geojson_to_s3")
@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_repair_raising_error_is_reported_as_failure(
    mock_source, mock_stored, mock_repair, visualization_config
):
    """An exception during repair becomes REPAIR_FAILED with type and message."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = bytes_io(json.dumps(STORED_DIFFERENT_GEOJSON))
    mock_repair.side_effect = RuntimeError("S3 bucket unavailable")

    output = run_command(repair="")

    assert "REPAIR_FAILED" in output
    assert "RuntimeError" in output
    assert "S3 bucket unavailable" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_positional_ids_limit_scope(
    mock_source, mock_stored, visualization_config, visualization_config_b
):
    """Positional VC ids restrict the run to exactly the named VCs."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    set_config(visualization_config_b, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = bytes_io(json.dumps(GENERATED_GEOJSON))

    output = run_command(vc_ids=[str(visualization_config_b.id)])

    assert output.count("vc=") == 1
    assert str(visualization_config_b.id) in output
    assert str(visualization_config.id) not in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_positional_ids_warn_on_unknown_uuid(mock_source, mock_stored, visualization_config):
    """An unknown UUID is warned about and the command still completes."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = bytes_io(json.dumps(GENERATED_GEOJSON))

    unknown = str(uuid.uuid4())
    output = run_command(vc_ids=[unknown])

    assert "WARNING" in output
    assert f"vc={unknown}" in output
    assert "not found" in output
    assert "Summary" in output


@patch("apps.shared_data.management.commands.verify_geojson_s3.upload_geojson_to_s3")
@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_repair_with_positional_ids_only_repairs_named_vcs(
    mock_source, mock_stored, mock_repair, visualization_config, visualization_config_kml
):
    """--repair composes with positional ids: only the named VC is touched."""
    set_config(visualization_config, geojson_s3_key="geojson/x/vc.geojson")
    mock_source.return_value = bytes_io(CSV_CONTENT)
    mock_stored.return_value = bytes_io(json.dumps(STORED_DIFFERENT_GEOJSON))
    mock_repair.return_value = REPAIRED_KEY

    output = run_command(repair="", vc_ids=[str(visualization_config.id)])

    mock_repair.assert_called_once_with(visualization_config.id)
    assert f"REPAIRED -> {REPAIRED_KEY}" in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch(
    "apps.shared_data.management.commands.verify_geojson_s3.get_geojson_from_data_entry",
    return_value=STORED_DIFFERENT_GEOJSON,
)
def test_positional_ids_bypass_type_scope_filter(
    mock_generate, mock_stored, visualization_config_gpx
):
    """Explicitly named out-of-scope VCs (e.g. GPX) are still checked."""
    set_config(visualization_config_gpx, geojson_s3_key="geojson/x/vc.geojson")
    mock_stored.return_value = bytes_io(json.dumps(GENERATED_GEOJSON))
    output = run_command(vc_ids=[str(visualization_config_gpx.id)])

    assert "DIFF" in output
    assert str(visualization_config_gpx.id) in output


@patch("apps.shared_data.services.geojson_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_out_of_scope_resource_types_are_skipped(mock_source, mock_stored, visualization_config):
    """Only dataset (csv/xls/xlsx) and KML/KMZ configs are checked."""
    set_config(visualization_config, geojson_s3_key=None)
    mock_source.return_value = bytes_io(CSV_CONTENT)
    # GPX is a GIS type but outside the command's scope: it must not appear.
    gpx_entry = DataEntry.objects.create(
        size=1,
        url=f"{settings.DATA_ENTRY_FILE_BASE_URL}/{visualization_config.created_by.id}/test_data.gpx",
        created_by=visualization_config.created_by,
        resource_type="gpx",
    )
    VisualizationConfig.objects.create(
        title="gpx viz",
        readable_id="zzzzzzzz",
        configuration=CONFIG,
        geojson_s3_key=None,
        data_entry=gpx_entry,
    )

    output = run_command()

    assert "gpx" not in output
    assert output.count("vc=") == 1
