import sys
from awsglue.transforms import *
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job
from pyspark.sql.functions import col

args = getResolvedOptions(sys.argv, ["JOB_NAME", "S3_INPUT_PATH", "MONGO_URI"])

sc = SparkContext()
glueContext = GlueContext(sc)
spark = glueContext.spark_session
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

# Read from S3
df = spark.read.option("header", "true").csv(args["S3_INPUT_PATH"])

# Transform: cast quantity from String to int
df = df.withColumn("quantity", col("quantity").cast("int"))

# Write / upsert to MongoDB Atlas (upsert on claim_id)
df.write \
    .format("mongodb") \
    .mode("append") \
    .option("spark.mongodb.write.connection.uri", args["MONGO_URI"]) \
    .option("database", "glueingestion") \
    .option("collection", "glueingestioncol") \
    .option("spark.mongodb.write.operationType", "replace") \
    .option("spark.mongodb.write.replaceDocument", "true") \
    .option("spark.mongodb.write.upsertDocument", "true") \
    .option("spark.mongodb.write.idFieldList", "claim_id") \
    .save()

job.commit()
