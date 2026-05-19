import csv
import random
import boto3
import io
from datetime import datetime, timedelta

BUCKET = "glue-source-may-18"
PREFIX = "data/simulated/"
NUM_FILES = 1000
ROWS_PER_FILE = 100

PHARMACIES = [
    ("Walgreens #1234", "TX", "1234567890"),
    ("CVS #5678", "CA", "2345678901"),
    ("Publix #1111", "FL", "6789012345"),
    ("Rite Aid #9999", "NY", "3456789012"),
    ("Costco Pharmacy", "WA", "4567890123"),
]
DRUGS = [
    ("68382-0103-01", "Amlodipine 5mg",   "Norvasc",    "GENERIC", "Y"),
    ("00071-0155-23", "Lisinopril 10mg",  "Prinivil",   "GENERIC", "Y"),
    ("00169-4175-11", "Metformin 500mg",  "Glucophage", "GENERIC", "Y"),
    ("00006-0072-54", "Atorvastatin 20mg","Lipitor",    "BRAND",   "N"),
    ("59148-0006-72", "Omeprazole 20mg",  "Prilosec",   "GENERIC", "Y"),
]
PRESCRIBERS = [
    ("1111111111", "DR. JAMES WILSON",   "Internal Medicine"),
    ("2222222222", "DR. SARAH JOHNSON",  "Cardiology"),
    ("3333333333", "SMITH, ROBERT MD",   "Endocrinology"),
    ("4444444444", "DR. EMILY CHEN",     "Family Medicine"),
    ("5555555555", "DR. MICHAEL BROWN",  "Neurology"),
]
STATUSES   = ["PAID", "REJECTED", "REVERSED", "PENDING"]
CLAIM_TYPES = ["MEDICAL", "DENTAL", "VISION"]
DIAG_CODES  = ["K21.0", "I10", "E11.9", "J45.20", "M54.5"]
TIERS       = ["1", "2", "3", "4"]
PLANS       = ["PLN-RX-BASIC", "PLN-SPEC-A", "PLN-PREM-B"]
GROUPS      = [f"GRP{10001 + i}" for i in range(10)]
BINS        = ["610502", "003858", "004336"]
PCNS        = ["RXPCN02", "ADV", "MEDCO"]
SOURCES     = ["CAREMARK", "OPTUMRX", "EXPRESSSCRIPTS"]

def rand_date(start="20250101", end="20250519"):
    s = datetime.strptime(start, "%Y%m%d")
    e = datetime.strptime(end,   "%Y%m%d")
    return (s + timedelta(days=random.randint(0, (e - s).days))).strftime("%Y%m%d")

def make_row(claim_num, file_idx):
    ph_name, ph_state, ph_npi = random.choice(PHARMACIES)
    ndc, drug, brand, dtype, generic = random.choice(DRUGS)
    presc_npi, presc_name, presc_spec = random.choice(PRESCRIBERS)
    status   = random.choice(STATUSES)
    qty      = random.choice([30, 60, 90])
    ing_cost = round(random.uniform(1.5, 150.0), 2)
    disp_fee = round(random.uniform(1.0, 5.0),   2)
    billed   = round(ing_cost + disp_fee + random.uniform(0, 10), 2)
    allowed  = round(billed * random.uniform(0.8, 1.0), 2)
    copay    = round(random.choice([5, 10, 20, 30, 50]), 2)
    plan_paid = round(max(0, allowed - copay), 2)
    ded      = round(random.uniform(0, 5), 2)
    oop      = round(ded + copay, 2)
    fill_dt  = rand_date()
    adj_dt   = rand_date(fill_dt)
    cob      = random.choice(["Y", "N"])
    cob_paid = round(random.uniform(0, 20), 2) if cob == "Y" else 0.00
    pa_num   = f"PA{random.randint(100000,999999)}" if random.random() < 0.2 else ""
    rej_code = str(random.randint(1, 99)) if status == "REJECTED" else ""
    rev_ind  = "Y" if status == "REVERSED" else "N"

    return {
        "claim_id":           f"CLM{claim_num:09d}",
        "member_id":          f"MBR{random.randint(1, 9999):07d}",
        "group_id":           random.choice(GROUPS),
        "plan_id":            random.choice(PLANS),
        "bin":                random.choice(BINS),
        "pcn":                random.choice(PCNS),
        "person_code":        random.choice(["01", "02", "03"]),
        "claim_type":         random.choice(CLAIM_TYPES),
        "claim_status":       status,
        "pharmacy_npi":       ph_npi,
        "pharmacy_name":      ph_name,
        "pharmacy_state":     ph_state,
        "dispensed_date":     fill_dt,
        "fill_date":          fill_dt,
        "drug_ndc":           ndc,
        "drug_name":          drug,
        "brand_name":         brand,
        "drug_type":          dtype,
        "generic_indicator":  generic,
        "quantity":           qty,
        "days_supply":        qty,
        "prescriber_npi":     presc_npi,
        "prescriber_name":    presc_name,
        "prescriber_specialty": presc_spec,
        "diagnosis_code":     random.choice(DIAG_CODES),
        "formulary_tier":     random.choice(TIERS),
        "ingredient_cost":    ing_cost,
        "dispensing_fee":     disp_fee,
        "billed_amount":      billed,
        "allowed_amount":     allowed,
        "plan_paid_amount":   plan_paid,
        "member_copay":       copay,
        "deductible_applied": ded,
        "oop_applied":        oop,
        "cob_indicator":      cob,
        "cob_paid_amount":    cob_paid,
        "prior_auth_number":  pa_num,
        "reject_code":        rej_code,
        "reversal_indicator": rev_ind,
        "submission_date":    fill_dt,
        "adjudication_date":  adj_dt,
        "batch_id":           f"BATCH-{fill_dt}-{file_idx:03d}",
        "source_system":      random.choice(SOURCES),
    }

HEADERS = list(make_row(0, 0).keys())

s3 = boto3.client("s3", region_name="us-east-1")
claim_counter = 2000000  # start after existing CLM001xxxxxx range
EXISTING_ID_RANGE = (1, 1999999)  # IDs already in MongoDB

for file_idx in range(1, NUM_FILES + 1):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=HEADERS)
    writer.writeheader()
    for _ in range(ROWS_PER_FILE):
        # ~30% chance to reuse an existing ID (update), else new ID (insert)
        if random.random() < 0.3:
            claim_num = random.randint(*EXISTING_ID_RANGE)
        else:
            claim_num = claim_counter
            claim_counter += 1
        writer.writerow(make_row(claim_num, file_idx))

    key = f"{PREFIX}claims_sim_{file_idx:04d}.csv"
    s3.put_object(Bucket=BUCKET, Key=key, Body=buf.getvalue())

    if file_idx % 100 == 0:
        print(f"Uploaded {file_idx}/{NUM_FILES} files...")

print(f"Done. {NUM_FILES} files uploaded to s3://{BUCKET}/{PREFIX}")
