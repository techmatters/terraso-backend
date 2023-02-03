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

import json
from base64 import b64decode

import jwt


class OpenID:
    def __init__(self, id_token):
        _raw_header, _raw_payload, _raw_sig = id_token.split(".")

        header_text = self._decode_b64(_raw_header)
        header = json.loads(header_text)

        self.data = jwt.decode(
            id_token, algorithms=header["alg"], options={"verify_signature": False}
        )

    @property
    def name(self):
        return self.data.get("name", "")

    @property
    def given_name(self):
        return self.data.get("given_name", "")

    @property
    def family_name(self):
        return self.data.get("family_name", "")

    @property
    def email(self):
        return self.data.get("email")

    @property
    def email_verified(self):
        return self.data.get("email_verified", False)

    @property
    def picture(self):
        return self.data.get("picture", "")

    def _decode_b64(self, data):
        missing_padding = len(data) % 4
        if missing_padding:
            return b64decode(data + "=" * missing_padding).decode()
        return b64decode(data).decode()
