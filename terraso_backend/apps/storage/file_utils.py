# Copyright © 2021-2023 Technology Matters
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
from apps.core.exceptions import ErrorContext, ErrorMessage
from django.http import JsonResponse
from dataclasses import asdict

def has_multiple_files(files):
    if len(files) > 1:
        return True
    return False


def is_file_upload_oversized(files, max_size, errorContextModel, errorContextField):
    if len(files) == 1:
        return get_file_size(files[0]) > max_size
    return False


def get_file_size(file):
    return file.size
