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
        return self.data.get("name")

    @property
    def given_name(self):
        return self.data.get("given_name")

    @property
    def family_name(self):
        return self.data.get("family_name")

    @property
    def email(self):
        return self.data.get("email")

    @property
    def email_verified(self):
        return self.data.get("email_verified")

    @property
    def picture(self):
        return self.data.get("picture")

    def _decode_b64(self, data):
        missing_padding = len(data) % 4
        if missing_padding:
            return b64decode(data + "=" * missing_padding).decode()
        return b64decode(data).decode()
