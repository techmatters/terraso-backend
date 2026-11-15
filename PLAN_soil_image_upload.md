# Plan: client image upload (DNG/JPG) to S3, keyed by site + depth

Branch: `feat/site-depth-image-upload`

## Goal & scope
Let a mobile client upload soil images (DNG, JPG) tied to a **site + depth
interval**, with **multiple images per site/depth** allowed. Initially for
**dev/testing**. Works against AWS S3 or the local silo unchanged (presigned
URLs resolve to whichever endpoint is configured; local just uses the LAN-IP
endpoint).

## Chosen approach (decisions confirmed)
- **Upload mechanism:** presigned PUT — client uploads bytes directly to S3.
- **Backend API:** GraphQL mutations (no bytes flow through the backend).

Rationale: DNG runs 10–60 MB; the existing through-backend path caps at
`MEDIA_UPLOAD_MAX_FILE_SIZE = 50 MB` and ties up a gunicorn worker for the whole
transfer. Presigned PUT avoids both. Note: this introduces presigned-PUT
generation, which the codebase does not do today (`get_signed_url` is read-only,
for serving files back) — so it is a new, additive pattern.

## Flow
```
1. Client → Backend (GraphQL):  requestSoilImageUploadUrl(site, depth, contentType)
                                 Backend authorizes, mints presigned S3 PUT URL + key
2. Client → S3 (HTTP PUT):      raw bytes straight to the presigned URL
3. Client → Backend (GraphQL):  (tentative) confirmSoilImageUpload(key) → DB row
```

## S3 key scheme — carries site+depth so it works even with no DB
```
soil-images/{site_id}/{depth_start}-{depth_end}/{uuid}.{ext}
e.g.  soil-images/9c3f.../0-10/1a2b3c.jpg
```
- `{uuid}` → multiple images per site/depth, no collisions.
- Prefix-listable: all images for a site/depth =
  `list_objects(prefix="soil-images/{site_id}/{start}-{end}/")`. This is what
  makes the DB optional for the dev phase.
- New bucket + settings `SOIL_IMAGES_S3_BUCKET` / `SOIL_IMAGES_BASE_URL`,
  mirroring the `PROFILE_IMAGES_* / DATA_ENTRY_* / STORY_MAP_MEDIA_*` groupings
  in `config/settings.py`.

## Phase 1 — buildable now (no DB)
1. **Storage class** `SoilImageStorage(TerrasoFileStorage)` in
   `apps/storage/s3.py`, bucket `SOIL_IMAGES_S3_BUCKET`.
2. **Service** `SoilImageUploadService` in `apps/storage/services.py`:
   - `generate_presigned_put_url(key, content_type)` — wraps
     `storage.bucket.meta.client.generate_presigned_url("put_object", ...)`.
   - reuse base `get_signed_url(key)` for read-back.
3. **Mint mutation** `requestSoilImageUploadUrl(siteId, depthStart, depthEnd,
   contentType)` → `{ uploadUrl, key }` in the soil_id (or storage) GraphQL
   schema.
4. **Authorization at mint time** — authenticated user + `rules` check that the
   user may access/modify that site's soil data (reuse `filter_visible_sites` /
   soil-data change predicate). This is the real gate: a presigned PUT grants
   write to that key.
5. **Content-type / extension allow-list** — `jpg/jpeg/dng` only. DNG often
   sniffs as TIFF via python-magic, so validate the declared extension/
   content-type at mint time rather than sniffing bytes.

Result: client can upload and we can find images by S3 prefix — usable without
any DB.

## Phase 2 — TENTATIVE (not built yet)
Only if listing-via-prefix proves insufficient.
- **Model** `SoilImage(BaseModel)`: `site` FK (leaning Site FK + raw
  `depth_start`/`depth_end` ints over a `SoilDataDepthInterval` FK, so ad-hoc dev
  images don't require a SoilData row + matching interval to pre-exist),
  `s3_key`, `content_type`, `size`, `created_by`, `created_at`.
- **Confirm mutation** `confirmSoilImageUpload(key)` → creates the row (step 3);
  optionally HEADs the object for real size/content-type.
- **Query** `soilImages(siteId, depthStart, depthEnd)` to list.

## Reference: existing conventions reused
- Base upload service / signed URLs: `apps/storage/services.py`
- S3 storage backends: `apps/storage/s3.py` (`TerrasoFileStorage`)
- Auth + rules: `apps/auth/mixins.py`, `apps/*/permission_rules.py`
- Site model: `apps/project_management/models/sites.py`
- Depth model: `apps/soil_id/models/depth_interval.py` (`SoilDataDepthInterval`)
- Settings groupings: `config/settings.py` (`*_S3_BUCKET`, `*_BASE_URL`)
