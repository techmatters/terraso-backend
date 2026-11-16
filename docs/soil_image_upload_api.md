# Soil image upload API (client guide)

Upload soil images (JPG / DNG) tied to a **site + depth interval**, via a
presigned S3 PUT. Two steps per image: ask the backend for a URL (GraphQL),
then upload the bytes straight to S3 (plain HTTP PUT). The bytes never pass
through the backend.

> Status: Phase 1 (dev/testing). No database record is kept yet — see
> [Limitations](#limitations).

## Step 1 — request a presigned upload URL (GraphQL)

Authenticated call (normal `Authorization: Bearer <jwt>`). One per image.

```graphql
mutation RequestSoilImageUploadUrl($input: SoilImageUploadUrlRequestInput!) {
  requestSoilImageUploadUrl(input: $input) {
    uploadUrl
    objectKey
    errors
  }
}
```

Variables:

```json
{
  "input": {
    "siteId": "<site-uuid>",
    "depthInterval": { "start": 0, "end": 10 },
    "contentType": "image/jpeg",
    "name": "main"
  }
}
```

### Inputs

| Field | Type | Notes |
|---|---|---|
| `siteId` | ID! | The site the image belongs to. Caller must have data-entry access to it. |
| `depthInterval` | `{ start: Int!, end: Int! }` | Depth interval in cm, e.g. `{start: 0, end: 10}`. |
| `contentType` | String! | One of `image/jpeg`, `image/x-adobe-dng`. Anything else → error. |
| `name` | String! | Short label for the image slot, e.g. `main`, `secondary`. `1–32` chars of `[A-Za-z0-9_-]`. |

### Response

| Field | Notes |
|---|---|
| `uploadUrl` | Short-lived (default 1 hour) presigned S3 **PUT** URL. Null on error. |
| `objectKey` | Where the object will live in S3 (see [key format](#object-key-format)). Null on error. |
| `errors` | Null on success; a list of `{message}` on failure. **Always check this** — on error both other fields are null. |

Errors you can get: not authenticated, no access to the site, unsupported
`contentType`, or invalid `name`.

## Step 2 — upload the bytes (plain HTTP PUT, not GraphQL)

```
PUT <uploadUrl>
Content-Type: image/jpeg        # MUST exactly match the contentType from step 1
<raw image bytes as the request body>
```

- **No `Authorization` header** on this request — the presigned URL carries its
  own auth.
- A `200` means it's stored.
- ⚠️ Most common failure: a missing/mismatched `Content-Type` header → S3 returns
  **`SignatureDoesNotMatch`**. It must byte-for-byte equal the `contentType` you
  sent in step 1.

## Object key format

```
soil-images/{siteId}/{depthStart}-{depthEnd}/{name}-{uuid}.{ext}

e.g.  soil-images/9c3f1b2a-…/0-10/main-1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d.jpg
```

The trailing `{uuid}` is random, so repeating the same site + depth + `name`
produces a **new** key each time — multiple images per slot never collide or
overwrite.

## Multiple images

Repeat steps 1–2 per image. Each call returns a unique `objectKey`.

## Content types

| Format | `contentType` to send |
|---|---|
| JPEG | `image/jpeg` |
| DNG (raw) | `image/x-adobe-dng` |

DNG has no official MIME type; `image/x-adobe-dng` is the agreed convention. If
the client library emits a different string for DNG, tell the backend team — the
allow-list is one line (`SOIL_IMAGE_ACCEPTED_CONTENT_TYPES`).

## Limitations (Phase 1)

- **No database record.** The backend does not persist anything about the
  upload; there is no confirm step.
- **No list/read API.** There's no endpoint to list or fetch a site's images
  yet. For now they're findable by S3 prefix (`soil-images/{siteId}/{start}-{end}/`).
- Reading an image back requires a signed GET URL (backend-side), not yet
  exposed via the API.

These are the deferred "Phase C" items (a `SoilImage` model + confirm/list/read
queries).

## Storage / config notes

- Bucket is set per environment via `SOIL_IMAGES_S3_BUCKET`. Local dev uses the
  silo bucket `terraso-local-soil-images`; real environments use a dedicated
  `terraso-{env}-soil-images` bucket (must be created in AWS + granted to the
  backend's IAM identity).
- Bucket is **private**; images are served via time-limited signed URLs, not
  public URLs.
