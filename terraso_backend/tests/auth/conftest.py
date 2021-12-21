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


@pytest.fixture
def access_tokens_apple():
    """
    Mocked data received from Apple.
    User email: testingterraso@example.com
    """
    return {
        "access_token": "a84fc9f185fd447d2983f62e65ec279f9.0.mwrw.9chaa92MIAqWQyx0HMrNXw",
        "refresh_token": "r01a474b1f7c540d7827a8ffdb6961403.0.mwrw.hqwZ3qScsKDS8JRNegHygQ",
        "token_type": "Bearer",
        "expires_in": 3600,
        "id_token": "eyJraWQiOiIxMjM0NSIsImFsZyI6IkhTNTEyIn0.eyJpc3MiOiJodHRwczovL2FwcGxlaWQuYXBwbGUuY29tIiwiYXVkIjoib3JnLnRlcnJhc28ubG9naW4iLCJleHAiOjE2NDAxNzY5MzcsImlhdCI6MTY0MDA5MDUzNywic3ViIjoiMDAwNjE2LjU2N2YyNmY3OGU5YzRlYzVwb2l3M2ViZjU2NzJkY2MyLjEyMzYiLCJhdF9oYXNoIjoiUEJUbEY2MlRLczBWVXR5RG93cGR1ciIsImVtYWlsIjoidGVzdGluZ3RlcnJhc29AZXhhbXBsZS5jb20iLCJlbWFpbF92ZXJpZmllZCI6InRydWUiLCJhdXRoX3RpbWUiOjE2NDAwOTA1MTQsIm5vbmNlX3N1cHBvcnRlZCI6dHJ1ZX0.tYliNF-lfpBgkPv2dq5RM44D8Pr6vISUd7RB1yIBa11E9klLXsApa6N_Le2nFFBaSkS0J3B1J_4eMkaj8HMaXw",  # noqa
    }
