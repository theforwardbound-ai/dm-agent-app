"""Northbeam Bank — a wholly fictional retail bank used as modelling input.

Six source systems, each aligned to BIAN business domains and service
domains. The alignment is illustrative — it follows BIAN's decomposition of
a bank into service domains so the resulting data products sit on recognised
capability boundaries, but it is not a certified BIAN mapping.

Everything here is synthetic. No real institution, customer or product.

Each system exposes a field inventory in the IDRA contract the agent reads:
    (Field Name, Data Type, Description, PII (Y/N), Entity Hint)
The Entity Hint is what lets the conceptual stage separate entities out of a
flat extract, so it carries real weight — keep it accurate.
"""
from dataclasses import dataclass

BANK_NAME = "Northbeam Bank"
BANK_CODE = "NBB"


@dataclass(frozen=True)
class SourceSystem:
    code: str
    name: str
    business_domain: str          # BIAN business domain
    service_domains: tuple        # BIAN service domains served
    frequency: str
    delivery: str
    grain_notes: str
    fields: tuple                 # (name, type, desc, pii, entity_hint)


# --------------------------------------------------------------------------
# CMD — Customer Master Data Management
# BIAN: Customer Management / Reference Data
# --------------------------------------------------------------------------
CMD_FIELDS = (
 ("PARTY_ID", "STRING", "Golden party surrogate key issued by MDM", "N", "party"),
 ("PARTY_SRC_SYS_CD", "STRING", "Contributing system of the surviving record", "N", "party"),
 ("PARTY_TYPE_CD", "STRING", "Party type (IND individual / ORG organisation)", "N", "party"),
 ("PARTY_LEGAL_NAME", "STRING", "Full legal name of the party", "Y", "party"),
 ("PARTY_BIRTH_DT", "DATE", "Date of birth (individuals only)", "Y", "party"),
 ("PARTY_TAX_ID", "STRING", "National tax identifier", "Y", "party"),
 ("PARTY_NATIONALITY_CD", "STRING", "ISO country code of nationality", "N", "party"),
 ("PARTY_RESIDENCY_CD", "STRING", "ISO country code of tax residency", "N", "party"),
 ("PARTY_STATUS_CD", "STRING", "Lifecycle status (ACTIVE/DORMANT/CLOSED)", "N", "party"),
 ("PARTY_SEGMENT_CD", "STRING", "Marketing segment (MASS/AFFLUENT/PRIVATE/SME)", "N", "party"),
 ("PARTY_KYC_STATUS_CD", "STRING", "KYC outcome (PASS/REFER/FAIL)", "N", "party"),
 ("PARTY_KYC_REVIEW_DT", "DATE", "Date KYC was last refreshed", "N", "party"),
 ("PARTY_RISK_RATING_CD", "STRING", "Financial crime risk rating (LOW/MED/HIGH)", "N", "party"),
 ("PARTY_PEP_FLG", "BOOLEAN", "Politically exposed person indicator", "Y", "party"),
 ("PARTY_ONBOARD_DT", "DATE", "Date the relationship was opened", "N", "party"),
 ("PARTY_LAST_UPDT_TS", "TIMESTAMP", "Last mastering update timestamp", "N", "party"),
 ("ADDR_ID", "STRING", "Address record identifier", "N", "party_address"),
 ("ADDR_PARTY_ID", "STRING", "Party the address belongs to", "N", "party_address"),
 ("ADDR_TYPE_CD", "STRING", "Address usage (RES/CORR/REG)", "N", "party_address"),
 ("ADDR_LINE_1", "STRING", "First line of the postal address", "Y", "party_address"),
 ("ADDR_CITY_NAME", "STRING", "City or town", "Y", "party_address"),
 ("ADDR_POSTAL_CD", "STRING", "Postal or ZIP code", "Y", "party_address"),
 ("ADDR_COUNTRY_CD", "STRING", "ISO country code", "N", "party_address"),
 ("ADDR_EFF_FROM_DT", "DATE", "Date the address became effective", "N", "party_address"),
 ("ADDR_EFF_TO_DT", "DATE", "Date the address ceased (null if current)", "N", "party_address"),
 ("CNTC_ID", "STRING", "Contact point identifier", "N", "party_contact"),
 ("CNTC_PARTY_ID", "STRING", "Party the contact point belongs to", "N", "party_contact"),
 ("CNTC_METHOD_CD", "STRING", "Contact method (EMAIL/MOBILE/PHONE)", "N", "party_contact"),
 ("CNTC_VALUE_TXT", "STRING", "Contact value as captured", "Y", "party_contact"),
 ("CNTC_VERIFIED_FLG", "BOOLEAN", "Whether the contact point is verified", "N", "party_contact"),
 ("REL_ID", "STRING", "Party-to-party relationship identifier", "N", "party_relationship"),
 ("REL_FROM_PARTY_ID", "STRING", "Originating party in the relationship", "N", "party_relationship"),
 ("REL_TO_PARTY_ID", "STRING", "Related party", "N", "party_relationship"),
 ("REL_TYPE_CD", "STRING", "Relationship type (SPOUSE/GUARANTOR/DIRECTOR)", "N", "party_relationship"),
)

# --------------------------------------------------------------------------
# DEP — Deposit system
# BIAN: Product Fulfilment — Current Account, Savings Account, Term Deposit
# --------------------------------------------------------------------------
DEP_FIELDS = (
 ("DEP_ACCT_ID", "STRING", "Deposit account surrogate key", "N", "deposit_account"),
 ("DEP_ACCT_NUM", "STRING", "Customer-facing account number", "Y", "deposit_account"),
 ("DEP_PARTY_ID", "STRING", "Primary owning party (MDM golden key)", "N", "deposit_account"),
 ("DEP_PROD_CD", "STRING", "Deposit product code", "N", "deposit_account"),
 ("DEP_PROD_TYPE_CD", "STRING", "Product family (CHQ current / SAV savings / TD term)", "N", "deposit_account"),
 ("DEP_CCY_CD", "STRING", "ISO currency of the account", "N", "deposit_account"),
 ("DEP_STATUS_CD", "STRING", "Account status (ACTIVE/DORMANT/CLOSED)", "N", "deposit_account"),
 ("DEP_OPEN_DT", "DATE", "Account opening date", "N", "deposit_account"),
 ("DEP_CLOSE_DT", "DATE", "Account closure date where applicable", "N", "deposit_account"),
 ("DEP_LEDGER_BAL_AMT", "DECIMAL(18,2)", "Ledger balance at extract", "N", "deposit_account"),
 ("DEP_AVAIL_BAL_AMT", "DECIMAL(18,2)", "Available balance at extract", "N", "deposit_account"),
 ("DEP_INT_RATE_PCT", "DECIMAL(9,4)", "Credit interest rate applied", "N", "deposit_account"),
 ("DEP_OVERDRAFT_LIMIT_AMT", "DECIMAL(18,2)", "Arranged overdraft limit (current accounts)", "N", "deposit_account"),
 ("DEP_TERM_MTHS", "INT", "Committed term in months (term deposits)", "N", "deposit_account"),
 ("DEP_MATURITY_DT", "DATE", "Maturity date (term deposits)", "N", "deposit_account"),
 ("DEP_BRANCH_CD", "STRING", "Servicing branch code", "N", "deposit_account"),
 ("DEP_OPEN_CHANNEL_CD", "STRING", "Channel the account was opened through", "N", "deposit_account"),
 ("DEP_JOINT_FLG", "BOOLEAN", "Whether the account is jointly held", "N", "deposit_account"),
 ("DEPH_ID", "STRING", "Daily balance snapshot identifier", "N", "deposit_balance_history"),
 ("DEPH_ACCT_ID", "STRING", "Deposit account the snapshot belongs to", "N", "deposit_balance_history"),
 ("DEPH_AS_OF_DT", "DATE", "Business date of the balance snapshot", "N", "deposit_balance_history"),
 ("DEPH_CLOSING_BAL_AMT", "DECIMAL(18,2)", "Closing ledger balance for the day", "N", "deposit_balance_history"),
 ("DEPH_ACCRUED_INT_AMT", "DECIMAL(18,2)", "Interest accrued but not yet paid", "N", "deposit_balance_history"),
)

# --------------------------------------------------------------------------
# LND — Lending system  (the first data product)
# BIAN: Product Fulfilment — Consumer Loan, Mortgage Loan, Credit Facility,
#       Collateral Asset Administration
# --------------------------------------------------------------------------
LND_FIELDS = (
 # origination
 ("APP_ID", "STRING", "Loan application identifier", "N", "loan_application"),
 ("APP_PARTY_ID", "STRING", "Applying party (MDM golden key)", "N", "loan_application"),
 ("APP_PROD_CD", "STRING", "Product applied for", "N", "loan_application"),
 ("APP_REQ_AMT", "DECIMAL(18,2)", "Amount requested by the applicant", "N", "loan_application"),
 ("APP_REQ_TERM_MTHS", "INT", "Term requested in months", "N", "loan_application"),
 ("APP_SUBMIT_TS", "TIMESTAMP", "When the application was submitted", "N", "loan_application"),
 ("APP_CHANNEL_CD", "STRING", "Origination channel (BRANCH/WEB/MOBILE/BROKER)", "N", "loan_application"),
 ("APP_STATUS_CD", "STRING", "Application status (DRAFT/SUBMITTED/DECIDED/WITHDRAWN)", "N", "loan_application"),
 ("APP_DECISION_CD", "STRING", "Underwriting decision (APPROVE/DECLINE/REFER)", "N", "loan_application"),
 ("APP_DECISION_TS", "TIMESTAMP", "When the decision was recorded", "N", "loan_application"),
 ("APP_DECLINE_RSN_CD", "STRING", "Decline reason code where declined", "N", "loan_application"),
 ("APP_CREDIT_SCORE", "INT", "Bureau credit score at decision", "Y", "loan_application"),
 ("APP_DTI_RATIO_PCT", "DECIMAL(9,4)", "Debt-to-income ratio at decision", "Y", "loan_application"),
 ("APP_DECLARED_INCOME_AMT", "DECIMAL(18,2)", "Gross annual income declared", "Y", "loan_application"),
 ("APP_OFFICER_ID", "STRING", "Underwriting officer identifier", "N", "loan_application"),
 # the loan itself
 ("LOAN_ID", "STRING", "Loan account surrogate key", "N", "loan_account"),
 ("LOAN_ACCT_NUM", "STRING", "Customer-facing loan account number", "Y", "loan_account"),
 ("LOAN_APP_ID", "STRING", "Originating application", "N", "loan_account"),
 ("LOAN_PARTY_ID", "STRING", "Borrowing party (MDM golden key)", "N", "loan_account"),
 ("LOAN_PROD_CD", "STRING", "Lending product code", "N", "loan_account"),
 ("LOAN_PROD_TYPE_CD", "STRING", "Product family (MORT/AUTO/PERS/HELOC/CARD)", "N", "loan_account"),
 ("LOAN_CCY_CD", "STRING", "ISO currency of the loan", "N", "loan_account"),
 ("LOAN_ORIG_AMT", "DECIMAL(18,2)", "Amount originally advanced", "N", "loan_account"),
 ("LOAN_ORIG_DT", "DATE", "Date the loan was drawn down", "N", "loan_account"),
 ("LOAN_MATURITY_DT", "DATE", "Contractual maturity date", "N", "loan_account"),
 ("LOAN_TERM_MTHS", "INT", "Contractual term in months", "N", "loan_account"),
 ("LOAN_INT_RATE_PCT", "DECIMAL(9,4)", "Current nominal interest rate", "N", "loan_account"),
 ("LOAN_RATE_TYPE_CD", "STRING", "Rate basis (FIXED/VARIABLE/TRACKER)", "N", "loan_account"),
 ("LOAN_STATUS_CD", "STRING", "Loan status (ACTIVE/CLOSED/WRITTEN_OFF)", "N", "loan_account"),
 ("LOAN_PRIN_BAL_AMT", "DECIMAL(18,2)", "Outstanding principal at extract", "N", "loan_account"),
 ("LOAN_ACCR_INT_AMT", "DECIMAL(18,2)", "Interest accrued and unpaid", "N", "loan_account"),
 ("LOAN_INSTALMENT_AMT", "DECIMAL(18,2)", "Contractual periodic instalment", "N", "loan_account"),
 ("LOAN_PAYMENT_FREQ_CD", "STRING", "Repayment frequency (MTH/QTR/ANN)", "N", "loan_account"),
 ("LOAN_NEXT_DUE_DT", "DATE", "Next contractual payment date", "N", "loan_account"),
 ("LOAN_DAYS_PAST_DUE", "INT", "Days past due at extract", "N", "loan_account"),
 ("LOAN_DELINQ_STAGE_CD", "STRING", "Arrears bucket (CURRENT/DPD30/DPD60/DPD90P)", "N", "loan_account"),
 ("LOAN_IMPAIRMENT_STAGE_CD", "STRING", "IFRS 9 impairment stage (1/2/3)", "N", "loan_account"),
 ("LOAN_ECL_AMT", "DECIMAL(18,2)", "Expected credit loss provision", "N", "loan_account"),
 ("LOAN_BRANCH_CD", "STRING", "Servicing branch code", "N", "loan_account"),
 ("LOAN_ORIG_CHANNEL_CD", "STRING", "Channel the loan originated through", "N", "loan_account"),
 # repayment schedule
 ("SCHD_ID", "STRING", "Schedule line identifier", "N", "repayment_schedule"),
 ("SCHD_LOAN_ID", "STRING", "Loan the schedule line belongs to", "N", "repayment_schedule"),
 ("SCHD_SEQ_NUM", "INT", "Instalment sequence number within the loan", "N", "repayment_schedule"),
 ("SCHD_DUE_DT", "DATE", "Date the instalment falls due", "N", "repayment_schedule"),
 ("SCHD_PRIN_AMT", "DECIMAL(18,2)", "Principal component of the instalment", "N", "repayment_schedule"),
 ("SCHD_INT_AMT", "DECIMAL(18,2)", "Interest component of the instalment", "N", "repayment_schedule"),
 ("SCHD_TOTAL_AMT", "DECIMAL(18,2)", "Total instalment due", "N", "repayment_schedule"),
 ("SCHD_PAID_FLG", "BOOLEAN", "Whether the instalment has been settled", "N", "repayment_schedule"),
 ("SCHD_PAID_DT", "DATE", "Date the instalment was settled", "N", "repayment_schedule"),
 # collateral
 ("COLL_ID", "STRING", "Collateral asset identifier", "N", "collateral"),
 ("COLL_LOAN_ID", "STRING", "Loan the collateral secures", "N", "collateral"),
 ("COLL_TYPE_CD", "STRING", "Collateral type (PROPERTY/VEHICLE/SECURITIES/CASH)", "N", "collateral"),
 ("COLL_DESC_TXT", "STRING", "Free-text description of the asset", "Y", "collateral"),
 ("COLL_VALUE_AMT", "DECIMAL(18,2)", "Assessed value of the collateral", "N", "collateral"),
 ("COLL_VALUATION_DT", "DATE", "Date of the latest valuation", "N", "collateral"),
 ("COLL_VALUATION_METHOD_CD", "STRING", "Valuation basis (FULL/DESKTOP/INDEXED)", "N", "collateral"),
 ("COLL_LTV_PCT", "DECIMAL(9,4)", "Loan-to-value at the latest valuation", "N", "collateral"),
 ("COLL_LIEN_POSITION_NUM", "INT", "Charge ranking held by the bank", "N", "collateral"),
 # credit facility
 ("FAC_ID", "STRING", "Credit facility identifier", "N", "credit_facility"),
 ("FAC_PARTY_ID", "STRING", "Party the facility is granted to", "N", "credit_facility"),
 ("FAC_TYPE_CD", "STRING", "Facility type (REVOLVING/TERM/OVERDRAFT)", "N", "credit_facility"),
 ("FAC_LIMIT_AMT", "DECIMAL(18,2)", "Approved facility limit", "N", "credit_facility"),
 ("FAC_UTILISED_AMT", "DECIMAL(18,2)", "Drawn amount against the limit", "N", "credit_facility"),
 ("FAC_APPROVED_DT", "DATE", "Date the facility was approved", "N", "credit_facility"),
 ("FAC_EXPIRY_DT", "DATE", "Facility expiry date", "N", "credit_facility"),
 ("FAC_STATUS_CD", "STRING", "Facility status (ACTIVE/SUSPENDED/EXPIRED)", "N", "credit_facility"),
)

# --------------------------------------------------------------------------
# TXN — Transaction processing
# BIAN: Operations — Payment Execution, Payment Order, Transaction Engine
# --------------------------------------------------------------------------
TXN_FIELDS = (
 ("TXN_ID", "STRING", "Transaction surrogate key", "N", "transaction"),
 ("TXN_ACCT_ID", "STRING", "Account the entry posts to", "N", "transaction"),
 ("TXN_ACCT_TYPE_CD", "STRING", "Account domain (DEPOSIT/LOAN)", "N", "transaction"),
 ("TXN_PARTY_ID", "STRING", "Party the account belongs to", "N", "transaction"),
 ("TXN_POST_DT", "DATE", "Business date the entry posted", "N", "transaction"),
 ("TXN_VALUE_DT", "DATE", "Value date for interest purposes", "N", "transaction"),
 ("TXN_BOOKING_TS", "TIMESTAMP", "Timestamp the entry was booked", "N", "transaction"),
 ("TXN_AMT", "DECIMAL(18,2)", "Signed transaction amount", "N", "transaction"),
 ("TXN_CCY_CD", "STRING", "ISO currency of the entry", "N", "transaction"),
 ("TXN_DR_CR_IND", "STRING", "Debit or credit indicator (D/C)", "N", "transaction"),
 ("TXN_TYPE_CD", "STRING", "Transaction type (PAYMENT/REPAYMENT/FEE/INTEREST)", "N", "transaction"),
 ("TXN_SUBTYPE_CD", "STRING", "Finer classification within the type", "N", "transaction"),
 ("TXN_CHANNEL_CD", "STRING", "Channel the transaction originated from", "N", "transaction"),
 ("TXN_PAYMENT_METHOD_CD", "STRING", "Payment rail (ACH/WIRE/CARD/DD/INTERNAL)", "N", "transaction"),
 ("TXN_COUNTERPARTY_NAME", "STRING", "Counterparty or merchant name", "Y", "transaction"),
 ("TXN_COUNTERPARTY_ACCT_REF", "STRING", "Counterparty account reference", "Y", "transaction"),
 ("TXN_MERCHANT_CATEGORY_CD", "STRING", "Merchant category code for card entries", "N", "transaction"),
 ("TXN_REF_NUM", "STRING", "End-to-end payment reference", "N", "transaction"),
 ("TXN_STATUS_CD", "STRING", "Settlement status (POSTED/PENDING/REVERSED)", "N", "transaction"),
 ("TXN_REVERSAL_FLG", "BOOLEAN", "Whether the entry reverses a prior posting", "N", "transaction"),
 ("TXN_ORIG_TXN_ID", "STRING", "Transaction reversed, where applicable", "N", "transaction"),
 ("TXN_BRANCH_CD", "STRING", "Branch attributed to the entry", "N", "transaction"),
)

# --------------------------------------------------------------------------
# BRN — Branch front end
# BIAN: Sales & Service — Branch Operations, Servicing Mandate
# --------------------------------------------------------------------------
BRN_FIELDS = (
 ("BRV_EVENT_ID", "STRING", "Branch servicing event identifier", "N", "branch_visit"),
 ("BRV_BRANCH_CD", "STRING", "Branch where the event occurred", "N", "branch_visit"),
 ("BRV_PARTY_ID", "STRING", "Party served (MDM golden key)", "N", "branch_visit"),
 ("BRV_TELLER_ID", "STRING", "Staff member who served the party", "N", "branch_visit"),
 ("BRV_EVENT_TS", "TIMESTAMP", "Timestamp the interaction started", "N", "branch_visit"),
 ("BRV_EVENT_TYPE_CD", "STRING", "Interaction type (TELLER/ADVISORY/ONBOARDING)", "N", "branch_visit"),
 ("BRV_SERVICE_CD", "STRING", "Service requested at the counter", "N", "branch_visit"),
 ("BRV_QUEUE_WAIT_SEC", "INT", "Seconds the party waited before being served", "N", "branch_visit"),
 ("BRV_DURATION_SEC", "INT", "Duration of the interaction in seconds", "N", "branch_visit"),
 ("BRV_OUTCOME_CD", "STRING", "Outcome (COMPLETED/REFERRED/ABANDONED)", "N", "branch_visit"),
 ("BRV_REFERRAL_PROD_CD", "STRING", "Product referred during the interaction", "N", "branch_visit"),
 ("BRV_APP_ID", "STRING", "Loan application raised from the visit", "N", "branch_visit"),
 ("BRN_BRANCH_CD", "STRING", "Branch code", "N", "branch"),
 ("BRN_BRANCH_NAME", "STRING", "Branch display name", "N", "branch"),
 ("BRN_REGION_CD", "STRING", "Region the branch reports into", "N", "branch"),
 ("BRN_CITY_NAME", "STRING", "City the branch is located in", "N", "branch"),
 ("BRN_COUNTRY_CD", "STRING", "ISO country code of the branch", "N", "branch"),
 ("BRN_OPEN_DT", "DATE", "Date the branch opened", "N", "branch"),
 ("BRN_STATUS_CD", "STRING", "Branch status (OPEN/CLOSED)", "N", "branch"),
)

# --------------------------------------------------------------------------
# DIG — Digital self-serve front end
# BIAN: Channel Operations — eBranch Operations, Customer Access Entitlement,
#       Party Authentication
# --------------------------------------------------------------------------
DIG_FIELDS = (
 ("SESS_ID", "STRING", "Digital session identifier", "N", "digital_session"),
 ("SESS_PARTY_ID", "STRING", "Authenticated party (MDM golden key)", "N", "digital_session"),
 ("SESS_CHANNEL_CD", "STRING", "Digital channel (WEB/MOBILE)", "N", "digital_session"),
 ("SESS_DEVICE_TYPE_CD", "STRING", "Device class (DESKTOP/TABLET/PHONE)", "N", "digital_session"),
 ("SESS_OS_NAME", "STRING", "Operating system reported by the client", "N", "digital_session"),
 ("SESS_START_TS", "TIMESTAMP", "Session start timestamp", "N", "digital_session"),
 ("SESS_END_TS", "TIMESTAMP", "Session end timestamp", "N", "digital_session"),
 ("SESS_AUTH_METHOD_CD", "STRING", "Authentication method (PWD/BIOMETRIC/MFA)", "N", "digital_session"),
 ("SESS_AUTH_RESULT_CD", "STRING", "Authentication outcome (SUCCESS/FAIL/LOCKED)", "N", "digital_session"),
 ("SESS_IP_ADDR", "STRING", "Client IP address at session start", "Y", "digital_session"),
 ("EVT_ID", "STRING", "Digital interaction event identifier", "N", "digital_event"),
 ("EVT_SESS_ID", "STRING", "Session the event belongs to", "N", "digital_event"),
 ("EVT_TS", "TIMESTAMP", "Timestamp of the event", "N", "digital_event"),
 ("EVT_TYPE_CD", "STRING", "Event type (PAGE_VIEW/QUOTE/APPLY_START/APPLY_SUBMIT)", "N", "digital_event"),
 ("EVT_PAGE_CD", "STRING", "Page or screen identifier", "N", "digital_event"),
 ("EVT_PROD_VIEWED_CD", "STRING", "Product the event relates to", "N", "digital_event"),
 ("EVT_APP_ID", "STRING", "Loan application started or advanced by the event", "N", "digital_event"),
 ("EVT_ABANDON_FLG", "BOOLEAN", "Whether the journey was abandoned at this step", "N", "digital_event"),
)


SYSTEMS: dict[str, SourceSystem] = {
 "CMD": SourceSystem(
   "CMD", "Customer Master Data Management",
   "Customer Management",
   ("Customer Reference Data Management", "Party Reference Data Directory",
    "Customer Relationship Management"),
   "Daily full snapshot", "Parquet",
   "Golden party records plus their addresses, contact points and "
   "party-to-party relationships. One row per party per extract date.",
   CMD_FIELDS),
 "DEP": SourceSystem(
   "DEP", "Deposit System",
   "Product Fulfilment",
   ("Current Account", "Savings Account", "Term Deposit"),
   "Daily delta plus daily balance snapshot", "Parquet",
   "One row per deposit account, with a separate daily closing-balance "
   "snapshot grain.",
   DEP_FIELDS),
 "LND": SourceSystem(
   "LND", "Lending System",
   "Product Fulfilment",
   ("Consumer Loan", "Mortgage Loan", "Credit Facility",
    "Collateral Asset Administration"),
   "Daily delta", "Parquet",
   "Applications, drawn loan accounts, contractual repayment schedules, "
   "collateral assets and credit facilities. Mixed grain — the conceptual "
   "stage must separate them.",
   LND_FIELDS),
 "TXN": SourceSystem(
   "TXN", "Transaction Processing System",
   "Operations and Execution",
   ("Payment Execution", "Payment Order", "Transaction Engine",
    "Financial Gateway"),
   "Intraday micro-batch", "Avro",
   "One row per posted financial entry against a deposit or loan account.",
   TXN_FIELDS),
 "BRN": SourceSystem(
   "BRN", "Branch Front End",
   "Sales and Service",
   ("Branch Operations", "Servicing Mandate", "Customer Case Management"),
   "Daily delta", "CSV",
   "Counter and advisory interactions, plus the branch reference list.",
   BRN_FIELDS),
 "DIG": SourceSystem(
   "DIG", "Digital Self-Serve Front End",
   "Channel Operations",
   ("eBranch Operations", "Customer Access Entitlement",
    "Party Authentication"),
   "Streaming, landed hourly", "JSON",
   "Authenticated digital sessions and the interaction events inside them, "
   "including lending application journeys.",
   DIG_FIELDS),
}


def build_idra(code: str, path: str) -> str:
    """Write one source system's IDRA in the contract the agent reads."""
    from openpyxl import Workbook
    sysdef = SYSTEMS[code]
    wb = Workbook()
    sh = wb.active
    sh.title = "Field Inventory"
    sh.append(["Field Name", "Data Type", "Description", "PII (Y/N)",
               "Entity Hint"])
    for row in sysdef.fields:
        sh.append(list(row))
    meta = wb.create_sheet("Extract Metadata")
    meta.append(["Bank", f"{BANK_NAME} ({BANK_CODE}) — fictional"])
    meta.append(["Source System", f"{sysdef.name} ({sysdef.code})"])
    meta.append(["BIAN Business Domain", sysdef.business_domain])
    meta.append(["BIAN Service Domains", "; ".join(sysdef.service_domains)])
    meta.append(["Frequency", sysdef.frequency])
    meta.append(["Delivery", sysdef.delivery])
    meta.append(["Grain Notes", sysdef.grain_notes])
    meta.append(["Field Count", len(sysdef.fields)])
    wb.save(path)
    return path


def entities(code: str) -> list[str]:
    """Distinct entity hints in declaration order."""
    seen, out = set(), []
    for f in SYSTEMS[code].fields:
        if f[4] not in seen:
            seen.add(f[4])
            out.append(f[4])
    return out


if __name__ == "__main__":
    for c, s in SYSTEMS.items():
        print(f"{c}  {s.name:38} {len(s.fields):3} fields  "
              f"entities: {', '.join(entities(c))}")
