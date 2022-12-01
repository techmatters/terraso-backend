# BACKUP / RESTORE

The Terraso backend optionally provides the ability to

- upload a Django object dump to an S3 bucket from an instance (the "Source" instance)
- download the object dump and restore the data to the database (the "Target" instance)
- trigger a wipe of the Target instance's DB from the Django admin panel, and restore the data from the Source instance

The last option is only supported if the Source instance is deployed as a Render Web Service, as the Render HTTP API is used to trigger the backup upload.

## Setup

In order to activate the backup/restore functionality, a few environment variables must be set

### Source Instance

- `DB_BACKUP_S3_BUCKET` must point to a S3 bucket where the backups will be stored
- The `AWS_*` credentials must be valid


### Target Instance

- The `ALLOW_RESTORE_FROM_BACKUP` should be set to `true`. This will make the button to trigger the job visible in the Django admin panel.
- The `DB_RESTORE_CONFIG_FILE` should point to the local of the restore configuration file.
- The restore configuration file is a file that allows you to set several variables.
  - The example is stored at [restore.conf](../../../../restore.conf)
  - The `service` block contains one property, `id`, which the Render ID of the Backend Service of the Source instance.
  - All other blocks will contain the bucket name and URL of all S3 buckets that should be synched. This also provides the information that will be used to rewrite URLs in the Target instance DB to point to the S3 buckets linked to the Target instance (i.e. change URLS in the database to point to `files.dev.terraso.org` instead of `files.terraso.org`)
- The `RENDER_API_TOKEN` should be set to your Render API token. This is used to make HTTP requests to the source instance and trigger the backup.


# Conclusion

With all of these steps completed, you should be able to access the Reset button from the Django admin page of the Target instance.
