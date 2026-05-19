# ETL Using AWS Glue: S3 to MongoDB Atlas

## Overview

This project provisions an AWS Glue PySpark ETL job that:
- Reads CSV data from an S3 bucket
- Transforms the `quantity` field from String to Integer
- Inserts/updates records into a MongoDB Atlas collection

---

## Architecture

```
S3 Bucket (glue-source-may-18)
        │
        │  CSV files (s3://glue-source-may-18/data/)
        ▼
AWS Glue Job (glue-mongodb-ingest)
        │  PySpark + MongoDB Spark Connector JAR
        │  Cast quantity: String → int
        ▼
MongoDB Atlas Cluster
  Database   : glueingestion
  Collection : glueingestioncol
```

---

## Project Structure

```
ETLUsingGlueS3ToMongoDB/
├── glue_job.py        # PySpark ETL script
├── glue_mongodb.tf    # Terraform infrastructure
└── README.md          # This file
```

---

## Prerequisites

### 1. MongoDB Atlas Network Access
In MongoDB Atlas → Network Access, add `0.0.0.0/0` (or the AWS Glue IP range for `us-east-1`) to allow inbound connections from Glue workers.

### 2. MongoDB Spark Connector JAR
Download the pre-built fat JAR from Maven Central:
```
https://repo1.maven.org/maven2/org/mongodb/spark/mongo-spark-connector_2.12/10.4.0/mongo-spark-connector_2.12-10.4.0-all.jar
```
Upload it to S3:
```bash
aws s3 cp mongo-spark-connector_2.12-10.4.0-all.jar s3://glue-source-may-18/jars/mongo-spark-connector.jar
```

### 3. Source Data
Upload your CSV files (with a `quantity` column) to:
```
s3://glue-source-may-18/data/
```

---

## Infrastructure (Terraform)

| Resource | Name | Purpose |
|---|---|---|
| `aws_iam_role` | glue-mongodb-role | Execution role for Glue job |
| `aws_iam_role_policy_attachment` | AWSGlueServiceRole | Managed policy for Glue |
| `aws_iam_role_policy` | glue-s3-access | S3 read/write on source bucket |
| `aws_s3_object` | glue_script | Uploads glue_job.py to S3 |
| `aws_glue_job` | glue-mongodb-ingest | PySpark ETL job definition |

---

## Glue Job Arguments

| Argument | Value | Description |
|---|---|---|
| `--S3_INPUT_PATH` | `s3://glue-source-may-18/data/` | S3 path to input CSV files |
| `--MONGO_URI` | `mongodb://<user>:<pass>@...` | Full MongoDB Atlas connection URI |
| `--extra-jars` | `s3://glue-source-may-18/jars/mongo-spark-connector.jar` | MongoDB Spark connector JAR |
| `--enable-continuous-cloudwatch-log` | `true` | Stream logs to CloudWatch |
| `--enable-job-insights` | `true` | Enable Glue job insights |

---

## Deployment

### Step 1 — Initialise Terraform
```bash
cd C:\Users\subbi\AWS\Glue\ETLUsingGlueS3ToMongoDB
terraform init
```

### Step 2 — Apply
```bash
terraform apply -var="db_username=<your_atlas_username>" -var="db_password=<your_atlas_password>"
```

### Step 3 — Run the Glue Job
Via AWS CLI:
```bash
aws glue start-job-run --job-name glue-mongodb-ingest
```
Or via AWS Console → Glue → Jobs → `glue-mongodb-ingest` → Run.

---

## Monitoring

- Logs: AWS Console → CloudWatch → Log Groups → `/aws-glue/jobs/output`
- Job history: AWS Console → Glue → Jobs → `glue-mongodb-ingest` → Run history
- Check job status via CLI:
```bash
aws glue get-job-run --job-name glue-mongodb-ingest --run-id <JobRunId>
```

---

## Transformation Logic

The `quantity` field is cast from String to Integer using PySpark:

```python
df = df.withColumn("quantity", col("quantity").cast("int"))
```

Rows where `quantity` cannot be parsed (e.g. empty string, non-numeric) will result in `null` for that field.

---

## MongoDB Target

| Property | Value |
|---|---|
| Cluster | `atlas-dr3e3x-shard-0` |
| Hosts | `ac-jippsc0-shard-00-00/01/02.vngeyfp.mongodb.net:27017` |
| Database | `glueingestion` |
| Collection | `glueingestioncol` |
| Auth Source | `admin` |
| SSL | Enabled |

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `ClassNotFoundException: MongoTableProvider` | JAR missing in S3 | Upload connector JAR to `s3://glue-source-may-18/jars/` |
| `Connection refused` / timeout | Atlas IP not whitelisted | Add `0.0.0.0/0` in Atlas Network Access |
| `Authentication failed` | Wrong credentials | Verify `db_username` / `db_password` in `terraform apply` |
| `Unable to resolve any valid connection` | Glue Connection attached to job | Remove `connections` block from `aws_glue_job` — connector handles it via URI |
