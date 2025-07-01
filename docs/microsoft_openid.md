# Description

Microsoft SSO requires a few extra steps to set up. These are detailed here.

Most of the steps have been taken from a guide on  [creating a self-signed SSL certificate](https://devcenter.heroku.com/articles/ssl-certificate-self#generate-private-key-and-certificate-signing-request).

## Creating a private key

The first step is to create a private key that will be used to sign the certificate uploaded to Azure. It will also be used to encrypt the JWT used to prove the identity to Microsoft.

```
openssl genrsa -aes256 -passout pass:gsahdg -out server.pass.key 4096
openssl rsa -passin pass:gsahdg -in server.pass.key -out server.key
rm server.pass.key
```

The private key `server.key` should be added as the private key env variable.

## Creating a certificate signing request

```
openssl req -new -key server.key -out server.csr
```

## Generate certificate

The `server.key` private key and `server.csr` can be used to create a certificate.

```
openssl x509 -req -sha256 -days 365 -in server.csr -signkey server.key -out server.crt
```

## Uploading certificate

Upload the certificate to Azure. Note the certificate thumbprint.

In Render, update
- MICROSOFT_CERTIFICATE_THUMBPRINT (from Azure)
- MICROSOFT_PRIVATE_KEY (contents of `server.key`)
