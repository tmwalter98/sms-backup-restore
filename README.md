# sms-backup-restore

This processes backups created by the SMS Backup & Restore app for Android and stores records in DynamoDB and S3.

## Usage

Dependencies are managed using [Poetry](https://python-poetry.org/).  They may be installed with

```
poetry install
```

### Running with local AWS resources using Docker Compose
The `docker-compose.yaml` enables local S3 using Minio, DynamoDB, along with DynamoDB Admin
```
docker-compose up -d
```
- Minio dashboard: [http://localhost:9000](http://localhost:9000)
- DynamoDB Admin dashboard: [http://localhost:8001](http://localhost:8001)

####
Configuring Minio bucket

### Deploying to AWS using CDK
