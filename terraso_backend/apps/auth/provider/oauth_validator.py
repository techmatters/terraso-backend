from oauth2_provider.oauth2_validators import OAuth2Validator


class TerrasoOAuth2Validator(OAuth2Validator):
    def get_additional_claims(self):
        return {
            "email": lambda request: request.user.email,
            "family_name": lambda request: request.user.last_name,
            "given_name": lambda request: request.user.first_name,
        }
