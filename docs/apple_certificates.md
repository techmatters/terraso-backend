# Apple identifiers, certificates and keys

We need identifiers, certificates and keys from Apple for two purposes:
* Sign in with Apple (web and native apps)
* Code signing (native apps)

## Sign in with Apple

The web app backend requires four variables/secrets to be set:

* `APPLE_TEAM_ID` (example: `2A8W5MT5NL`; from [account details](https://developer.apple.com/account#MembershipDetailsCard))
* `APPLE_CLIENT_ID` (example: `org.terraso.app`; see "Create an app ID")
* `APPLE_KEY_ID` (example: `ZNGJBXR2QR`; see "Get a private key")
* `APPLE_PRIVATE_KEY` (starts with `-----BEGIN PRIVATE KEY-----\nMIGT…`; see "Get a private key")

### Create an app ID
1. Go to https://developer.apple.com/account/resources/identifiers/add/bundleId
1. Click App IDs
1. Click Continue
1. Click App
1. Click Continue
1. Fill in Description
1. Fill in Bundle ID
1. Click Sign In with Apple
1. Click Configure
1. Click Save
1. Click Continue
1. Click Register


### Get a private key
1. Go to https://developer.apple.com/account/resources/authkeys/add
1. Fill in Key Name
1. Check Sign in with Apple
1. Click Configure
1. Select Primary App ID > App ID
1. Click Save
1. Click Continue
1. Click Register
1. Click Download (AuthKey_[keyid].p8)


## Code signing

The GitHub CI service requires seven variables/secrets to be set:

For building and signing:

* `APPLE_TEAM_ID` (example: `2A8W5MT5NL`; from [account details](https://developer.apple.com/account#MembershipDetailsCard))
* `APPLE_CERTIFICATE_PASSWORD` from 1Password
* `APPLE_MOBILE_PROVISION_BASE64` (see "Get a provisioning profile")
* `APPLE_P12_BASE64` (see "Get a distibution certificate")

For uploading to the app store:

* `APPLE_ISSUER_ID` from [integrations/api](https://appstoreconnect.apple.com/access/integrations/api)
* `APPLE_KEY_ID` from [integrations/api](https://appstoreconnect.apple.com/access/integrations/api)
* `APPLE_APP_STORE_CONNECT_PRIVATE_KEY` (starts with `-----BEGIN PRIVATE KEY-----\nMIGT…`; see "Get an App Store Connect API key")

### Generate a certificate signing request (CSR)
1. Open Keychain Access
1. Select Keychain Access > Certificate Assistant > Request a Certificate From a Certificate Authority…
1. Fill in the "User Email Address" and "Common Name" and select "Saved to disk."
1. Click Continue
1. Save the file to disk.

### Get a distibution certificate

1. Go to [Add Certificate](https://developer.apple.com/account/resources/certificates/add)
1. Click "iOS Distribution"
1. Click Continue
1. Click "Choose File" and select the file you created in 1.4.
1. Click Continue
1. Click Download
1. Double-click the downloaded file (ios_distribution.cer) and open it in Keychain Access
1. Select the certificate (iPhone Distribution XYZ)
1. Select File > Export Items
1. Click Save (Certificates.p12)
1. Fill in Password and Verify
1. Click OK
1. Convert to base64 (`base64 -i Certificates.p12 -o certificates.txt`)

### Get a provisioning profile

1. Go to [Add Profile](https://developer.apple.com/account/resources/profiles/add)
1. Click "App Store Connect"
1. Click Continue
1. Select App ID > [your app]
1. Click Continue
1. Select the certificate you created in 2.5
1. Click Continue
1. Fill in "Provisioning Profile name" (MyApp)
1. Click Generate
1. Click Download (MyApp.mobileProvision)
1. Convert to base64 (`base64 -i MyApp.mobileprovision -o profile.txt`)

### Get an App Store Connect API key
1. Go to [Add API Key](https://appstoreconnect.apple.com/access/integrations/api/new)
1. Fill out Name (i.e. MyApp API Key)
1. Select Access > Developer
1. Click Generate
1. Click Download (AuthKey_[keyid].p8)
