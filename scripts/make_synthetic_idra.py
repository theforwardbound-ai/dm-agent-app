"""Fully synthetic IDRA for a fictional 'RetailCoreBanking' extract.
No bank content — safe for personal infrastructure."""
import sys
from openpyxl import Workbook

FIELDS = [
 ("CUST_ID","STRING","Customer surrogate identifier","N","customer"),
 ("CUST_FULL_NAME","STRING","Customer legal name","Y","customer"),
 ("CUST_SEGMENT_CD","STRING","Retail segment code","N","customer"),
 ("CUST_OPEN_DT","DATE","Relationship open date","N","customer"),
 ("ACCT_ID","STRING","Account surrogate identifier","N","account"),
 ("ACCT_TYPE_CD","STRING","Product type code (CHQ/SAV/CARD)","N","account"),
 ("ACCT_STATUS_CD","STRING","Account status","N","account"),
 ("ACCT_OPEN_DT","DATE","Account open date","N","account"),
 ("ACCT_CURR_BAL_AMT","DECIMAL(18,2)","Current balance","N","account"),
 ("ACCT_CUST_ID","STRING","Owning customer id","N","account"),
 ("TXN_ID","STRING","Transaction identifier","N","transaction"),
 ("TXN_ACCT_ID","STRING","Account id of the posting","N","transaction"),
 ("TXN_POST_DT","DATE","Posting date","N","transaction"),
 ("TXN_AMT","DECIMAL(18,2)","Signed transaction amount","N","transaction"),
 ("TXN_TYPE_CD","STRING","Debit/credit type code","N","transaction"),
 ("TXN_CHANNEL_CD","STRING","Origination channel","N","transaction"),
 ("TXN_MERCH_NAME","STRING","Merchant name where applicable","Y","transaction"),
]

def build(path: str):
    wb = Workbook()
    sh = wb.active; sh.title = "Field Inventory"
    sh.append(["Field Name","Data Type","Description","PII (Y/N)","Entity Hint"])
    for row in FIELDS: sh.append(list(row))
    meta = wb.create_sheet("Extract Metadata")
    meta.append(["Source System","RetailCoreBanking (synthetic)"])
    meta.append(["Frequency","Daily"]); meta.append(["Delivery","Parquet"])
    wb.save(path)
    print(f"synthetic IDRA written: {path} ({len(FIELDS)} fields)")

if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "synthetic_idra.xlsx")
