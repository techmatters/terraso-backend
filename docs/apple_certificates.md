# Sign in with Apple

- Client ID (APPLE_CLIENT_ID) (org.terraso.app)

Bundle ID from 1.7

- Key ID (APPLE_KEY_ID) (ZNGJBXR2QR)

From 2.8

- Private Key (APPLE_PRIVATE_KEY) (-----BEGIN PRIVATE KEY-----\nMIGT....)

From 2.8

- Team ID (APPLE_TEAM_ID) (2A8W5MT5NL)

Get this from https://developer.apple.com/account#MembershipDetailsCard


1. Create an app ID
1.1 Go to https://developer.apple.com/account/resources/identifiers/add/bundleId
1.2 Click App IDs
1.3 Click Continue
1.4 Click App
1.5 Click Continue
1.6 Fill in Description
1.7 Fill in Bundle ID
1.8 Click Sign In with Apple
1.9 Click Configure
1.10 Click Save
1.11 Click Continue
1.12 Click Register


2. Get a private key
2.1 Go to https://developer.apple.com/account/resources/authkeys/add
2.2 Fill in Key Name
2.3 Check Sign in with Apple
2.3 Click Configure
2.4 Select Primary App ID > App ID
2.5 Click Save
2.6 Click Continue
2.7 Click Register
2.8 Click Download (AuthKey_[keyid].p8)




# App code signing

APPLE_ISSUER_ID

Get this from https://appstoreconnect.apple.com/access/integrations/api

APPLE_KEY_ID

Get this from https://appstoreconnect.apple.com/access/integrations/api

APPLE_PRIVATE_KEY

* Team ID (IOS_TEAM_ID)

Get this from https://developer.apple.com/account#MembershipDetailsCard

* Profile (IOS_MOBILE_PROVISION_BASE64)

base64 -i MyApp.mobileprovision -o profile.txt

* Certificate (IOS_P12_BASE64)

base64 -i Certificates.p12 -o certificates.txt

* Certificate password (IOS_CERTIFICATE_PASSWORD)

This is stored in 1Password.

1. Generate a certificate signing request (CSR)
1.1 Open Keychain Access
1.2 Select Keychain Access > Certificate Assistant > Request a Certificate From a Certificate Authority…
1.3 Fill in the "User Email Address" and "Common Name" and select "Saved to disk."
1.4 Click Continue
1.5 Save the file to disk.

2. Get a distibution certificate
2.1 Go to https://developer.apple.com/account/resources/certificates/add
2.2 Click "iOS Distribution"
2.3 Click Continue
2.4 Click "Choose File" and select the file you created in 1.4.
2.5 Click Continue
2.6 Click Download
2.7 Double-click the downloaded file (ios_distribution.cer) and open it in Keychain Access
2.8 Select the certificate (iPhone Distribution XYZ)
2.9 Select File > Export Items
2.10 Click Save (Certificates.p12)
2.11 Fill in Password and Verify
2.12 Click OK

3. Get a provisioning profile
3.1 Go to https://developer.apple.com/account/resources/profiles/add
3.2 Click "App Store Connect"
3.3 Click Continue
3.4 Select App ID > [your app]
3.5 Click Continue
3.6 Select the certificate you created in 2.5
3.7 Click Continue
3.8 Fill in "Provisioning Profile name"
3.9 Click Generate
3.10 Click Download (MyApp.mobileProvision)

4. Get an App Store Connect API key
4.1 Go to https://appstoreconnect.apple.com/access/integrations/api/new
4.2 Fill out Name (i.e. MyApp API Key)
4.3 Select Access > Developer
4.4 Click Generate
4.5 Click Download (AuthKey_keyid.p8)
