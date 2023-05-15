# E2E Test users

# Define a test user

Go to the admin interface to `/admin/e2e_tests/testuser/` to define a test user.

# Get session ID

1. Go to `/admin`
2. Login to admin panel
3. Gather `sessionid` cookie value

# Generate a token

Using the admin graphql endpoint execute the follwing query:

GraphQL mutation:
```graphql
mutation {
  generateTestUserToken(input: { userEmail: "[test user email]"}) {
    errors
    token
  }
}
```

Curl command:
```bash
curl '[host]/graphql/admin' \
  -H 'cookie: sessionid=[admin session ID]' \
  -H 'accept: application/json, multipart/mixed' \
  -H 'content-type: application/json' \
  --data-raw '{"query":"mutation { generateTestUserToken(input: { userEmail: \"[test user email]\"}) { errors token } }"}'
```
