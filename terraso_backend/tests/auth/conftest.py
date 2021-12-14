import pytest


@pytest.fixture
def access_tokens_google():
    """
    Mocked data received from Google.
    User name: Testing Terraso
    User email: testingterraso@example.com
    """
    return {
        "access_token": "opaque-access-token",
        "expires_in": 3599,
        "refresh_token": "opaque-refresh-token",
        "scope": "openid https://www.googleapis.com/auth/userinfo.email https://www.googleapis.com/auth/userinfo.profile",  # noqa
        "token_type": "Bearer",
        "id_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJodHRwczovL2FjY291bnRzLmdvb2dsZS5jb20iLCJhenAiOiI4ODYwOTkzMTgyNzQtNDN2bGdmaGlmdDk1YWdncGgxdGRyc2VsM2tuNW1wbTAuYXBwcy5nb29nbGV1c2VyY29udGVudC5jb20iLCJhdWQiOiI4ODYwOTkzODI3NC00M3ZsZ2ZoaWZ0OTVhZ2dwaDF0ZHJzZWwza241bXBtMC5hcHBzLmdvb2dsZXVzZXJjb250ZW50LmNvbSIsInN1YiI6IjEwODkzMTgyNzQ3NzM4MjgwMjkiLCJlbWFpbCI6InRlc3Rpbmd0ZXJyYXNvQGV4YW1wbGUuY29tIiwiZW1haWxfdmVyaWZpZWQiOnRydWUsImF0X2hhc2giOiJkcnpRcjFpUzFoQ1BYcGtFeHdzMDZnIiwibmFtZSI6IlRlc3RpbmcgVGVycmFzbyIsInBpY3R1cmUiOiJodHRwczovL2xoMy5nb29nbGV1c2VyY29udGVudC5jb20vYS0vYWFhSkpKbmV4am5uZG1mTVE3b2RqUFAyWDAzbVV6WVNaLWNSd0kzbjJXNEFRPXM5Ni1jIiwiZ2l2ZW5fbmFtZSI6IlRlc3RpbmciLCJmYW1pbHlfbmFtZSI6IlRlcnJhc28iLCJsb2NhbGUiOiJlbiIsImlhdCI6MTYzOTQxNjAyNywiZXhwIjoxNjM5NDE5NjI3fQ.fXj-d9GJ8E9IQnML7F1iAPFeRIyBQ4GEu_OC3tJlKCM",  # noqa
    }
