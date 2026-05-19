terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# ── Variables ────────────────────────────────────────────────────────────────

variable "db_username" {
  description = "MongoDB Atlas username"
  type        = string
  sensitive   = true
}

variable "db_password" {
  description = "MongoDB Atlas password"
  type        = string
  sensitive   = true
}

# ── S3 bucket for Glue scripts ───────────────────────────────────────────────

resource "aws_s3_object" "glue_script" {
  bucket = "glue-source-may-18"
  key    = "scripts/glue_job.py"
  source = "${path.module}/glue_job.py"
  etag   = filemd5("${path.module}/glue_job.py")
}

# ── IAM Role for Glue ────────────────────────────────────────────────────────

resource "aws_iam_role" "glue_role" {
  name = "glue-mongodb-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "glue.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "glue_service" {
  role       = aws_iam_role.glue_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSGlueServiceRole"
}

resource "aws_iam_role_policy" "glue_s3_access" {
  name = "glue-s3-access"
  role = aws_iam_role.glue_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["s3:GetObject", "s3:ListBucket", "s3:PutObject"]
      Resource = [
        "arn:aws:s3:::glue-source-may-18",
        "arn:aws:s3:::glue-source-may-18/*"
      ]
    }]
  })
}

# ── Glue Job ─────────────────────────────────────────────────────────────────

locals {
  mongo_uri = "mongodb://${var.db_username}:${var.db_password}@ac-jippsc0-shard-00-00.vngeyfp.mongodb.net:27017,ac-jippsc0-shard-00-01.vngeyfp.mongodb.net:27017,ac-jippsc0-shard-00-02.vngeyfp.mongodb.net:27017/?ssl=true&replicaSet=atlas-dr3e3x-shard-0&authSource=admin&appName=Cluster0free"
}

resource "aws_glue_job" "mongodb_ingest" {
  name         = "glue-mongodb-ingest"
  role_arn     = aws_iam_role.glue_role.arn
  glue_version = "4.0"
  worker_type  = "G.1X"
  number_of_workers = 2

  command {
    name            = "glueetl"
    script_location = "s3://glue-source-may-18/scripts/glue_job.py"
    python_version  = "3"
  }

  default_arguments = {
    "--S3_INPUT_PATH"                    = "s3://glue-source-may-18/data/simulated/"
    "--MONGO_URI"                        = local.mongo_uri
    "--extra-jars"                       = "s3://glue-source-may-18/jars/mongo-spark-connector.jar"
    "--job-language"                     = "python"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-job-insights"              = "true"
  }

  execution_property {
    max_concurrent_runs = 1
  }
}

# ── Outputs ──────────────────────────────────────────────────────────────────

output "glue_job_name" {
  value = aws_glue_job.mongodb_ingest.name
}
