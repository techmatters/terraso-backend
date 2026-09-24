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

import io
import json
from unittest.mock import patch

import pytest

from apps.shared_data.geojson_upload import (
    _resolve_column_index,
    get_geojson_from_data_entry,
    get_rows_from_file,
    upload_geojson_to_s3,
    upload_geojson_to_s3_precreate,
)
from apps.shared_data.models import VisualizationConfig

pytestmark = pytest.mark.django_db


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.geojson_upload_service.upload_file_get_path")
def test_upload_geojson_to_s3_dataset_success(
    mock_upload_path, mock_get_file, visualization_config
):
    """Dataset CSV upload generates correct GeoJSON and stores the S3 key."""
    visualization_config.configuration = {
        "datasetConfig": {
            "longitude": "lng",
            "latitude": "lat",
        },
        "annotateConfig": {
            "dataPoints": [
                {
                    "label": "label",
                    "column": "col1",
                }
            ]
        },
    }
    visualization_config.save()
    mock_get_file.return_value = io.BytesIO(
        b"lat,lng,col1\n-78.48306234911033,-0.1805502450716432,val3"
    )
    mock_upload_path.return_value = "geojson/test-id/test-vc-id.geojson"

    result = upload_geojson_to_s3(visualization_config.id)

    updated_vc = VisualizationConfig.objects.get(id=visualization_config.id)
    assert updated_vc.geojson_s3_key == "geojson/test-id/test-vc-id.geojson"
    assert result == "geojson/test-id/test-vc-id.geojson"
    mock_upload_path.assert_called_once()

    # Verify the GeoJSON content that was uploaded
    call_args = mock_upload_path.call_args
    pos_args, kwargs = call_args
    uploaded_file = kwargs.get("file", pos_args[1])
    uploaded_content = json.loads(uploaded_file.read().decode("utf-8"))
    assert uploaded_content["type"] == "FeatureCollection"
    assert len(uploaded_content["features"]) == 1
    assert uploaded_content["features"][0]["geometry"]["coordinates"] == [
        -0.1805502450716432,
        -78.48306234911033,
    ]


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.geojson_upload_service.upload_file_get_path")
def test_upload_geojson_to_s3_dataset_uses_first_column_as_annotation_title(
    mock_upload_path, mock_get_file, visualization_config
):
    expected_title = "First marker"
    visualization_config.configuration = {
        "datasetConfig": {
            "longitude": "lng",
            "latitude": "lat",
        },
        "annotateConfig": {
            "annotationTitle": "Title",
            "dataPoints": [],
        },
    }
    visualization_config.save()
    mock_get_file.return_value = io.StringIO(
        f"Title,lat,lng\n{expected_title},-78.48306234911033,-0.1805502450716432"
    )
    mock_upload_path.return_value = "geojson/test-id/test-vc-id.geojson"

    upload_geojson_to_s3(visualization_config.id)

    uploaded_file = mock_upload_path.call_args.args[1]
    uploaded_content = json.loads(uploaded_file.read().decode("utf-8"))
    assert uploaded_content["features"][0]["properties"]["title"] == expected_title


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_upload_geojson_to_s3_no_geojson(mock_get_file, visualization_config):
    """When resource type is not spreadsheet or GIS, returns None without crashing."""
    visualization_config.data_entry.resource_type = "pdf"
    visualization_config.data_entry.save()

    result = upload_geojson_to_s3(visualization_config.id)

    assert result is None
    updated_vc = VisualizationConfig.objects.get(id=visualization_config.id)
    assert updated_vc.geojson_s3_key is None


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.geojson_upload_service.upload_file_get_path")
def test_upload_geojson_to_s3_cleans_up_old_key(
    mock_upload_path, mock_get_file, visualization_config
):
    """When VC already has a geojson_s3_key, the old key's file is deleted."""
    visualization_config.configuration = {
        "datasetConfig": {
            "longitude": "lng",
            "latitude": "lat",
        },
        "annotateConfig": {
            "dataPoints": [
                {
                    "label": "label",
                    "column": "col1",
                }
            ]
        },
    }
    visualization_config.geojson_s3_key = "geojson/old-id/old-file.geojson"
    visualization_config.save()
    mock_get_file.return_value = io.BytesIO(
        b"lat,lng,col1\n-78.48306234911033,-0.1805502450716432,val3"
    )
    mock_upload_path.return_value = "geojson/new-id/new-file.geojson"

    with patch("apps.shared_data.geojson_upload.geojson_upload_service.delete_file") as mock_delete:
        result = upload_geojson_to_s3(visualization_config.id)

    mock_delete.assert_called_once_with("geojson/old-id/old-file.geojson")
    updated_vc = VisualizationConfig.objects.get(id=visualization_config.id)
    assert updated_vc.geojson_s3_key == "geojson/new-id/new-file.geojson"
    assert result == "geojson/new-id/new-file.geojson"


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.geojson_upload_service.upload_file_get_path")
def test_upload_geojson_to_s3_precreate_dataset_success(
    mock_upload_path, mock_get_file, visualization_config
):
    """upload_geojson_to_s3_precreate uploads GeoJSON and returns S3 key."""
    from apps.shared_data.geojson_upload import upload_geojson_to_s3_precreate

    vc = visualization_config
    vc.configuration = {
        "datasetConfig": {
            "longitude": "lng",
            "latitude": "lat",
        },
        "annotateConfig": {
            "dataPoints": [
                {
                    "label": "label",
                    "column": "col1",
                }
            ]
        },
    }
    vc.save()

    mock_get_file.return_value = io.BytesIO(
        b"lat,lng,col1\n-78.48306234911033,-0.1805502450716432,val3"
    )
    mock_upload_path.return_value = "geojson/test-uuid/test-uuid.geojson"

    result = upload_geojson_to_s3_precreate(
        "test-uuid", vc.data_entry, json.dumps(vc.configuration)
    )

    assert result == "geojson/test-uuid/test-uuid.geojson"


# ---------------------------------------------------------------------------
# get_rows_from_file: CSV decoding (BOM, encoding) and delimiter handling
# ---------------------------------------------------------------------------


def make_csv_bytes(text):
    return io.BytesIO(text.encode("utf-8"))


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_rows_from_file_strips_utf8_bom(mock_get_file, data_entry):
    """BOM-prefixed CSV decodes via utf-8-sig; header has no U+FEFF."""
    mock_get_file.return_value = make_csv_bytes(
        "\ufeffObs ID,User name,Longitude,Latitude\nobs1,Doe,-77.95,-1.65\n"
    )

    rows = get_rows_from_file(data_entry)

    assert rows[0] == ["Obs ID", "User name", "Longitude", "Latitude"]
    assert rows[1] == ["obs1", "Doe", "-77.95", "-1.65"]


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_rows_from_file_semicolon_quoted_headers(mock_get_file, data_entry):
    """Semicolon-delimited CSV with fully quoted headers re-parses columns."""
    mock_get_file.return_value = make_csv_bytes(
        '"start";"end";"Localización";"_Localización_longitude"\n"r1";"end";"loc";"-77.95"\n'
    )

    rows = get_rows_from_file(data_entry)

    assert rows[0] == ["start", "end", "Localización", "_Localización_longitude"]
    assert rows[1] == ["r1", "end", "loc", "-77.95"]


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_rows_from_file_semicolon_unquoted_headers(mock_get_file, data_entry):
    """Unquoted semicolon-delimited headers (ID;Longitud_X;Latitud_Y) parse."""
    mock_get_file.return_value = make_csv_bytes("ID;Longitud_X;Latitud_Y\n1;-77.95;-1.65\n")

    rows = get_rows_from_file(data_entry)

    assert rows[0] == ["ID", "Longitud_X", "Latitud_Y"]
    assert rows[1] == ["1", "-77.95", "-1.65"]


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_rows_from_file_tab_delimited(mock_get_file, data_entry):
    """Tab-delimited CSV re-parses when the comma parse yields one column."""
    mock_get_file.return_value = make_csv_bytes(
        "Obs ID\tLongitude\tLatitude\nobs1\t-77.95\t-1.65\n"
    )

    rows = get_rows_from_file(data_entry)

    assert rows[0] == ["Obs ID", "Longitude", "Latitude"]
    assert rows[1] == ["obs1", "-77.95", "-1.65"]


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_rows_from_file_comma_csv_unchanged(mock_get_file, data_entry):
    """Plain comma CSV keeps the default dialect (no false re-sniffing)."""
    mock_get_file.return_value = make_csv_bytes("lat,lng,col1\n-78.48,-0.18,val3\n")

    rows = get_rows_from_file(data_entry)

    assert rows == [["lat", "lng", "col1"], ["-78.48", "-0.18", "val3"]]


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_rows_from_file_sniffer_failure_falls_back_to_semicolon(mock_get_file, data_entry):
    """Input the Sniffer cannot classify falls back to ';' (csv.Error path)."""
    # 'Lat;Long notes' + a non-numeric second row defeats csv.Sniffer on 3.13.
    mock_get_file.return_value = make_csv_bytes("Lat;Long notes\n-77.95\n")

    rows = get_rows_from_file(data_entry)

    assert rows == [["Lat", "Long notes"], ["-77.95"]]


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_rows_from_file_empty_file_returns_empty(mock_get_file, data_entry):
    """0-byte and BOM-only files yield no rows instead of IndexError."""
    mock_get_file.return_value = make_csv_bytes("")
    assert get_rows_from_file(data_entry) == []

    mock_get_file.return_value = make_csv_bytes("\ufeff")
    assert get_rows_from_file(data_entry) == []


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.geojson_upload_service.upload_file_get_path")
def test_upload_geojson_to_s3_bom_csv_converts(
    mock_upload_path, mock_get_file, visualization_config
):
    """BOM-prefixed CSV converts end-to-end with exact column matches."""
    visualization_config.configuration = {
        "datasetConfig": {"longitude": "Longitude", "latitude": "Latitude"},
        "annotateConfig": {"dataPoints": [{"label": "Obs ID", "column": "Obs ID"}]},
    }
    visualization_config.save()
    mock_get_file.return_value = make_csv_bytes(
        "\ufeffObs ID,Longitude,Latitude\nobs1,-77.95,-1.65\n"
    )
    mock_upload_path.return_value = "geojson/test-id/test-vc-id.geojson"

    upload_geojson_to_s3(visualization_config.id)

    updated_vc = VisualizationConfig.objects.get(id=visualization_config.id)
    assert updated_vc.geojson_s3_key == "geojson/test-id/test-vc-id.geojson"
    call_args = mock_upload_path.call_args
    pos_args, kwargs = call_args
    uploaded_file = kwargs.get("file", pos_args[1])
    uploaded_content = json.loads(uploaded_file.read().decode("utf-8"))
    assert len(uploaded_content["features"]) == 1
    assert uploaded_content["features"][0]["geometry"]["coordinates"] == [-77.95, -1.65]


# ---------------------------------------------------------------------------
# Column resolution and tolerant dataset conversion
# ---------------------------------------------------------------------------


def build_config(longitude, latitude, data_points, annotation_title=None):
    return {
        "datasetConfig": {"longitude": longitude, "latitude": latitude},
        "annotateConfig": {"dataPoints": data_points, "annotationTitle": annotation_title},
    }


def set_vc_config(visualization_config, config):
    visualization_config.configuration = config
    visualization_config.save()


def test_resolve_column_index_matching_tiers():
    """Exact, trimmed, normalized and mojibake tiers all resolve."""
    header = [
        "\ufeffObs ID",
        "Técnico ",
        "Number of Pine Tree Seedlings Given ",
        "_Localización_longitude",
    ]

    assert _resolve_column_index(header, "\ufeffObs ID") == 0  # exact
    assert _resolve_column_index(header, "Obs ID") == 0  # BOM stripped
    assert _resolve_column_index(header, "Técnico") == 1  # strip both sides
    assert _resolve_column_index(header, "técnico ") == 1  # casefold
    assert _resolve_column_index(header, "TÃ©cnico ") == 1  # mojibake repair
    assert (
        _resolve_column_index(header, "Number of Pine Tree Seedlings Given") == 2
    )  # trailing space
    assert _resolve_column_index(header, "_LocalizaciÃ³n_longitude") == 3  # mojibake
    assert _resolve_column_index(header, "No Such Column") is None


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_geojson_from_data_entry_exact_shape(mock_get_file, visualization_config):
    """FeatureCollection output shape is preserved exactly."""
    set_vc_config(
        visualization_config,
        build_config("Longitude", "Latitude", [{"label": "Name", "column": "Name"}]),
    )
    mock_get_file.return_value = make_csv_bytes("Name,Longitude,Latitude\nsite,-77.95,-1.65\n")

    geojson = get_geojson_from_data_entry(visualization_config.data_entry, visualization_config)

    assert geojson == {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-77.95, -1.65]},
                "properties": {
                    "title": None,
                    "fields": json.dumps([{"label": "Name", "value": "site"}]),
                },
            }
        ],
    }


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_geojson_from_data_entry_mojibake_column_resolves(mock_get_file, visualization_config):
    """Mojibake config name ('TÃ©cnico ') resolves against proper header ('Técnico ')."""
    set_vc_config(
        visualization_config,
        build_config("Longitude", "Latitude", [{"label": "TÃ©cnico ", "column": "TÃ©cnico "}]),
    )
    mock_get_file.return_value = make_csv_bytes("Técnico ,Longitude,Latitude\nAna,-77.95,-1.65\n")

    geojson = get_geojson_from_data_entry(visualization_config.data_entry, visualization_config)

    assert len(geojson["features"]) == 1
    assert json.loads(geojson["features"][0]["properties"]["fields"]) == [
        {"label": "TÃ©cnico ", "value": "Ana"}
    ]


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_geojson_from_data_entry_trailing_space_header_resolves(
    mock_get_file, visualization_config
):
    """Trimmed config name resolves against a header with a trailing space."""
    set_vc_config(
        visualization_config,
        build_config("Longitude", "Latitude", [{"label": "Given", "column": "Given"}]),
    )
    mock_get_file.return_value = make_csv_bytes("Given ,Longitude,Latitude\n12,-77.95,-1.65\n")

    geojson = get_geojson_from_data_entry(visualization_config.data_entry, visualization_config)

    assert json.loads(geojson["features"][0]["properties"]["fields"]) == [
        {"label": "Given", "value": "12"}
    ]


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_geojson_from_data_entry_semicolon_mojibake_and_decimal_comma(
    mock_get_file, visualization_config
):
    """Mojibake lon/lat config + semicolon CSV + comma-decimal coordinates."""
    set_vc_config(
        visualization_config,
        build_config(
            "_LocalizaciÃ³n_longitude",
            "_LocalizaciÃ³n_latitude",
            [{"label": "Foto", "column": "Foto"}],
        ),
    )
    mock_get_file.return_value = make_csv_bytes(
        '"_Localización_longitude";"_Localización_latitude";"Foto"\n'
        '"-77,9522722";"-1,654625";"foto.jpg"\n'
    )

    geojson = get_geojson_from_data_entry(visualization_config.data_entry, visualization_config)

    assert geojson["features"][0]["geometry"]["coordinates"] == [-77.9522722, -1.654625]
    assert json.loads(geojson["features"][0]["properties"]["fields"]) == [
        {"label": "Foto", "value": "foto.jpg"}
    ]


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_geojson_from_data_entry_unresolvable_data_point_skipped(
    mock_get_file, visualization_config
):
    """An unresolvable dataPoint is skipped; resolvable ones still emit fields."""
    set_vc_config(
        visualization_config,
        build_config(
            "Longitude",
            "Latitude",
            [
                {"label": "Name", "column": "Name"},
                {"label": "Ghost", "column": "Missing Column"},
            ],
        ),
    )
    mock_get_file.return_value = make_csv_bytes("Name,Longitude,Latitude\nsite,-77.95,-1.65\n")

    geojson = get_geojson_from_data_entry(visualization_config.data_entry, visualization_config)

    assert len(geojson["features"]) == 1
    assert json.loads(geojson["features"][0]["properties"]["fields"]) == [
        {"label": "Name", "value": "site"}
    ]


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_geojson_from_data_entry_unresolvable_title_is_none(
    mock_get_file, visualization_config
):
    """An unresolvable annotationTitle yields title None, not a crash."""
    set_vc_config(
        visualization_config,
        build_config(
            "Longitude",
            "Latitude",
            [{"label": "Name", "column": "Name"}],
            annotation_title="Missing Title",
        ),
    )
    mock_get_file.return_value = make_csv_bytes("Name,Longitude,Latitude\nsite,-77.95,-1.65\n")

    geojson = get_geojson_from_data_entry(visualization_config.data_entry, visualization_config)

    assert geojson["features"][0]["properties"]["title"] is None


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_geojson_from_data_entry_bom_header_resolves(mock_get_file, visualization_config):
    """Config 'Obs ID' resolves against a BOM-prefixed header."""
    set_vc_config(
        visualization_config,
        build_config("Longitude", "Latitude", [{"label": "Obs ID", "column": "Obs ID"}]),
    )
    mock_get_file.return_value = make_csv_bytes(
        "\ufeffObs ID,Longitude,Latitude\nobs1,-77.95,-1.65\n"
    )

    geojson = get_geojson_from_data_entry(visualization_config.data_entry, visualization_config)

    assert json.loads(geojson["features"][0]["properties"]["fields"]) == [
        {"label": "Obs ID", "value": "obs1"}
    ]


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_geojson_from_data_entry_empty_latitude_returns_none(
    mock_get_file, visualization_config
):
    """Config latitude '' (prod case) returns None instead of crashing."""
    set_vc_config(
        visualization_config,
        build_config("Longitude", "", [{"label": "Name", "column": "Name"}]),
    )
    mock_get_file.return_value = make_csv_bytes("Name,Longitude\nsite,-77.95\n")

    result = get_geojson_from_data_entry(visualization_config.data_entry, visualization_config)

    assert result is None


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_geojson_from_data_entry_unparseable_coords_returns_none(
    mock_get_file, visualization_config
):
    """All rows with unparseable coordinates: 0 features -> None."""
    set_vc_config(
        visualization_config,
        build_config("Longitude", "Latitude", [{"label": "Name", "column": "Name"}]),
    )
    mock_get_file.return_value = make_csv_bytes("Name,Longitude,Latitude\nsite,notanum,alsobad\n")

    result = get_geojson_from_data_entry(visualization_config.data_entry, visualization_config)

    assert result is None


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_geojson_from_data_entry_nan_coords_skipped(mock_get_file, visualization_config):
    """NaN cells (blank xls cells) are not coordinates: skip the row."""
    set_vc_config(
        visualization_config,
        build_config("Longitude", "Latitude", [{"label": "Name", "column": "Name"}]),
    )
    mock_get_file.return_value = make_csv_bytes(
        "Name,Longitude,Latitude\nbad,nan,nan\nok,-77.95,-1.65\n"
    )

    geojson = get_geojson_from_data_entry(visualization_config.data_entry, visualization_config)

    assert len(geojson["features"]) == 1


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_geojson_from_data_entry_plus_sign_decimal_comma(mock_get_file, visualization_config):
    """'+1,5' (explicit sign, comma decimal) parses as a coordinate."""
    set_vc_config(
        visualization_config,
        build_config("Longitude", "Latitude", [{"label": "Name", "column": "Name"}]),
    )
    mock_get_file.return_value = make_csv_bytes('Name,Longitude,Latitude\nsite,-77.95,"+1,65"\n')

    geojson = get_geojson_from_data_entry(visualization_config.data_entry, visualization_config)

    assert geojson["features"][0]["geometry"]["coordinates"] == [-77.95, 1.65]


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
def test_get_geojson_from_data_entry_empty_file_rejects_cleanly(
    mock_get_file, visualization_config
):
    """Empty file: precreate raises ValueError (clean reject), no IndexError."""
    set_vc_config(
        visualization_config,
        build_config("Longitude", "Latitude", [{"label": "Name", "column": "Name"}]),
    )
    mock_get_file.return_value = make_csv_bytes("")

    with pytest.raises(ValueError):
        upload_geojson_to_s3_precreate(
            "test-uuid", visualization_config.data_entry, visualization_config.configuration
        )


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.geojson_upload_service.upload_file_get_path")
def test_upload_geojson_to_s3_precreate_raises_on_missing_geojson(
    mock_upload_path, mock_get_file, visualization_config
):
    """precreate raises ValueError when geojson generation yields None."""
    set_vc_config(
        visualization_config,
        build_config("Longitude", "", [{"label": "Name", "column": "Name"}]),
    )
    mock_get_file.return_value = make_csv_bytes("Name,Longitude\nsite,-77.95\n")

    with pytest.raises(ValueError):
        upload_geojson_to_s3_precreate(
            "test-uuid", visualization_config.data_entry, visualization_config.configuration
        )

    mock_upload_path.assert_not_called()


@patch("apps.shared_data.geojson_upload.data_entry_upload_service.get_file")
@patch("apps.shared_data.geojson_upload.geojson_upload_service.upload_file_get_path")
def test_upload_geojson_to_s3_keeps_existing_key_when_no_geojson(
    mock_upload_path, mock_get_file, visualization_config
):
    """Update path: None geojson -> returns None, existing S3 key untouched."""
    set_vc_config(
        visualization_config,
        build_config("Longitude", "", [{"label": "Name", "column": "Name"}]),
    )
    visualization_config.geojson_s3_key = "geojson/old-id/keep.geojson"
    visualization_config.save()
    mock_get_file.return_value = make_csv_bytes("Name,Longitude\nsite,-77.95\n")

    result = upload_geojson_to_s3(visualization_config.id)

    assert result is None
    mock_upload_path.assert_not_called()
    updated_vc = VisualizationConfig.objects.get(id=visualization_config.id)
    assert updated_vc.geojson_s3_key == "geojson/old-id/keep.geojson"
