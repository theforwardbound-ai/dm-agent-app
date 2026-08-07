"""Synthetic extracts for Northbeam Bank's six source systems.

Referential integrity is the point: MDM parties drive deposit accounts, loan
applications and loans; loans drive schedules and collateral; transactions
post against real accounts; branch and digital events reference real parties
and real applications. A model built on these extracts can be validated by
actually running the generated ETL, not just eyeballed.

Every row is fabricated. Names are assembled from syllables so they cannot
collide with real people.

    python scripts/make_bank_data.py [outdir]
"""
import csv
import datetime as dt
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.bank_sources import SYSTEMS, BANK_CODE   # noqa: E402

SEED = 20260807
random.seed(SEED)

TODAY = dt.date(2026, 8, 1)
CCY = "GBP"

N_PARTY, N_DEP, N_APP, N_TXN = 400, 620, 320, 6000
N_BRANCH, N_VISIT, N_SESSION = 24, 700, 1100
BAL_DAYS = 10

SYL_A = ["Ar", "Bel", "Cor", "Dan", "El", "Fen", "Gar", "Hal", "Im", "Jor",
         "Kel", "Lir", "Mor", "Nev", "Or", "Pel", "Quen", "Ral", "Sor", "Tan"]
SYL_B = ["and", "ith", "or", "wen", "dar", "lin", "mos", "ric", "ven", "tal"]
SURN = ["Ashdown", "Brackley", "Corvale", "Dunmore", "Ellerby", "Fairholt",
        "Garrow", "Hensley", "Ivensen", "Jarrow", "Kelbourne", "Lindmere",
        "Marchcroft", "Northolt", "Orvale", "Pemberton", "Quarrow",
        "Rathbone", "Stanmore", "Thurlow", "Underhill", "Vancroft"]
CITIES = ["Ashford", "Beckton", "Calderly", "Dunwich", "Everton", "Fenwick",
          "Granton", "Harlow", "Ilkeston", "Jarrowby", "Kelso", "Lyndhurst"]


def name():
    return (f"{random.choice(SYL_A)}{random.choice(SYL_B)} "
            f"{random.choice(SURN)}")


def d(base, lo, hi):
    return base + dt.timedelta(days=random.randint(lo, hi))


def ts(day, lo=7, hi=20):
    return dt.datetime.combine(day, dt.time(random.randint(lo, hi),
                                            random.randint(0, 59),
                                            random.randint(0, 59)))


def money(lo, hi):
    return round(random.uniform(lo, hi), 2)


def pct(lo, hi):
    return round(random.uniform(lo, hi), 4)


# --------------------------------------------------------------------------
BRANCHES = [f"BR{i:03d}" for i in range(1, N_BRANCH + 1)]
PARTY_IDS = [f"P{i:07d}" for i in range(1, N_PARTY + 1)]

rows: dict[str, list[dict]] = {}


def add(entity, row):
    rows.setdefault(entity, []).append(row)


# ---------- CMD ----------
party_type, party_seg = {}, {}
for pid in PARTY_IDS:
    typ = "ORG" if random.random() < 0.12 else "IND"
    party_type[pid] = typ
    seg = random.choices(["MASS", "AFFLUENT", "PRIVATE", "SME"],
                         [0.62, 0.22, 0.06, 0.10])[0]
    party_seg[pid] = seg
    onboard = d(TODAY, -4000, -60)
    add("party", {
        "PARTY_ID": pid, "PARTY_SRC_SYS_CD": random.choice(["DEP", "LND", "BRN"]),
        "PARTY_TYPE_CD": typ, "PARTY_LEGAL_NAME": name(),
        "PARTY_BIRTH_DT": (d(TODAY, -25000, -6600) if typ == "IND" else ""),
        "PARTY_TAX_ID": f"TX{random.randint(10**8, 10**9 - 1)}",
        "PARTY_NATIONALITY_CD": random.choices(["GB", "IE", "FR", "DE"],
                                               [0.8, 0.08, 0.06, 0.06])[0],
        "PARTY_RESIDENCY_CD": "GB",
        "PARTY_STATUS_CD": random.choices(["ACTIVE", "DORMANT", "CLOSED"],
                                          [0.88, 0.08, 0.04])[0],
        "PARTY_SEGMENT_CD": seg,
        "PARTY_KYC_STATUS_CD": random.choices(["PASS", "REFER", "FAIL"],
                                              [0.93, 0.06, 0.01])[0],
        "PARTY_KYC_REVIEW_DT": d(TODAY, -900, -10),
        "PARTY_RISK_RATING_CD": random.choices(["LOW", "MED", "HIGH"],
                                               [0.75, 0.21, 0.04])[0],
        "PARTY_PEP_FLG": random.random() < 0.015,
        "PARTY_ONBOARD_DT": onboard,
        "PARTY_LAST_UPDT_TS": ts(d(TODAY, -120, 0)),
    })
    for i, atype in enumerate(["RES"] + (["CORR"] if random.random() < 0.2 else [])):
        add("party_address", {
            "ADDR_ID": f"A{pid[1:]}{i}", "ADDR_PARTY_ID": pid,
            "ADDR_TYPE_CD": atype,
            "ADDR_LINE_1": f"{random.randint(1, 240)} {random.choice(SURN)} "
                           f"{random.choice(['Road', 'Street', 'Lane'])}",
            "ADDR_CITY_NAME": random.choice(CITIES),
            "ADDR_POSTAL_CD": f"{random.choice('ABCDEFGHLMNSW')}"
                              f"{random.randint(1, 29)} "
                              f"{random.randint(1, 9)}{random.choice('ABDEFGH')}"
                              f"{random.choice('ABDEFGH')}",
            "ADDR_COUNTRY_CD": "GB",
            "ADDR_EFF_FROM_DT": d(onboard, 0, 400),
            "ADDR_EFF_TO_DT": "",
        })
    for j, m in enumerate(["EMAIL", "MOBILE"]):
        add("party_contact", {
            "CNTC_ID": f"C{pid[1:]}{j}", "CNTC_PARTY_ID": pid,
            "CNTC_METHOD_CD": m,
            "CNTC_VALUE_TXT": (f"user{pid[1:]}@example.invalid" if m == "EMAIL"
                               else f"+44700{random.randint(100000, 999999)}"),
            "CNTC_VERIFIED_FLG": random.random() < 0.85,
        })
for k in range(80):
    a, b = random.sample(PARTY_IDS, 2)
    add("party_relationship", {
        "REL_ID": f"R{k:06d}", "REL_FROM_PARTY_ID": a, "REL_TO_PARTY_ID": b,
        "REL_TYPE_CD": random.choice(["SPOUSE", "GUARANTOR", "DIRECTOR"]),
    })

# ---------- DEP ----------
dep_ids = []
for i in range(1, N_DEP + 1):
    aid = f"D{i:07d}"
    dep_ids.append(aid)
    pid = random.choice(PARTY_IDS)
    ptype = random.choices(["CHQ", "SAV", "TD"], [0.5, 0.38, 0.12])[0]
    opened = d(TODAY, -3200, -30)
    closed = d(opened, 60, 900) if random.random() < 0.07 else ""
    bal = money(50, 48000) if ptype != "TD" else money(2000, 90000)
    term = random.choice([6, 12, 24, 36]) if ptype == "TD" else ""
    add("deposit_account", {
        "DEP_ACCT_ID": aid, "DEP_ACCT_NUM": f"6{random.randint(10**7, 10**8 - 1)}",
        "DEP_PARTY_ID": pid, "DEP_PROD_CD": f"{ptype}-{random.randint(1, 4):02d}",
        "DEP_PROD_TYPE_CD": ptype, "DEP_CCY_CD": CCY,
        "DEP_STATUS_CD": "CLOSED" if closed else
                         random.choices(["ACTIVE", "DORMANT"], [0.93, 0.07])[0],
        "DEP_OPEN_DT": opened, "DEP_CLOSE_DT": closed,
        "DEP_LEDGER_BAL_AMT": bal,
        "DEP_AVAIL_BAL_AMT": round(bal - money(0, 200), 2),
        "DEP_INT_RATE_PCT": pct(0.05, 4.75),
        "DEP_OVERDRAFT_LIMIT_AMT": (money(200, 3000) if ptype == "CHQ" else 0),
        "DEP_TERM_MTHS": term,
        "DEP_MATURITY_DT": (d(opened, term * 30, term * 30) if term else ""),
        "DEP_BRANCH_CD": random.choice(BRANCHES),
        "DEP_OPEN_CHANNEL_CD": random.choices(
            ["BRANCH", "WEB", "MOBILE"], [0.42, 0.33, 0.25])[0],
        "DEP_JOINT_FLG": random.random() < 0.18,
    })
    if i <= 250:
        run = bal
        for k in range(BAL_DAYS):
            day = TODAY - dt.timedelta(days=k)
            run = round(run + money(-900, 900), 2)
            add("deposit_balance_history", {
                "DEPH_ID": f"H{i:07d}{k:02d}", "DEPH_ACCT_ID": aid,
                "DEPH_AS_OF_DT": day, "DEPH_CLOSING_BAL_AMT": run,
                "DEPH_ACCRUED_INT_AMT": round(abs(run) * 0.0001 * (k + 1), 2),
            })

# ---------- LND ----------
PROD = {"MORT": (60000, 620000, 240, 360), "AUTO": (4000, 48000, 36, 84),
        "PERS": (1000, 26000, 12, 60), "HELOC": (10000, 120000, 60, 180),
        "CARD": (500, 14000, 12, 24)}
app_ids, loan_ids, approved = [], [], []
for i in range(1, N_APP + 1):
    app = f"APP{i:06d}"
    app_ids.append(app)
    pid = random.choice(PARTY_IDS)
    ptype = random.choices(list(PROD), [0.22, 0.24, 0.32, 0.09, 0.13])[0]
    lo, hi, tlo, thi = PROD[ptype]
    submit = d(TODAY, -1100, -20)
    score = random.randint(430, 900)
    decision = ("APPROVE" if score > 640 and random.random() < 0.86
                else random.choices(["DECLINE", "REFER"], [0.75, 0.25])[0])
    status = random.choices(["DECIDED", "WITHDRAWN"], [0.94, 0.06])[0]
    add("loan_application", {
        "APP_ID": app, "APP_PARTY_ID": pid,
        "APP_PROD_CD": f"{ptype}-{random.randint(1, 3):02d}",
        "APP_REQ_AMT": money(lo, hi),
        "APP_REQ_TERM_MTHS": random.randint(tlo, thi),
        "APP_SUBMIT_TS": ts(submit),
        "APP_CHANNEL_CD": random.choices(
            ["BRANCH", "WEB", "MOBILE", "BROKER"], [0.3, 0.3, 0.24, 0.16])[0],
        "APP_STATUS_CD": status,
        "APP_DECISION_CD": decision if status == "DECIDED" else "",
        "APP_DECISION_TS": ts(d(submit, 0, 9)) if status == "DECIDED" else "",
        "APP_DECLINE_RSN_CD": (random.choice(["AFFORD", "BUREAU", "POLICY",
                                              "DOCS"])
                               if decision == "DECLINE" else ""),
        "APP_CREDIT_SCORE": score,
        "APP_DTI_RATIO_PCT": pct(5, 58),
        "APP_DECLARED_INCOME_AMT": money(18000, 210000),
        "APP_OFFICER_ID": f"U{random.randint(100, 399)}",
    })
    if status == "DECIDED" and decision == "APPROVE":
        approved.append((app, pid, ptype, submit))

for n, (app, pid, ptype, submit) in enumerate(approved, 1):
    lid = f"L{n:07d}"
    loan_ids.append(lid)
    lo, hi, tlo, thi = PROD[ptype]
    orig = money(lo, hi)
    term = random.randint(tlo, thi)
    start = d(submit, 3, 40)
    dpd = random.choices([0, 12, 45, 75, 120], [0.82, 0.07, 0.05, 0.03, 0.03])[0]
    bucket = ("CURRENT" if dpd == 0 else "DPD30" if dpd < 31 else
              "DPD60" if dpd < 61 else "DPD90P")
    stage = "1" if dpd == 0 else "2" if dpd < 90 else "3"
    paid_ratio = random.uniform(0.02, 0.85)
    prin = round(orig * (1 - paid_ratio), 2)
    rate = pct(2.1, 12.4) if ptype != "CARD" else pct(14.9, 29.9)
    inst = round((orig / term) * (1 + rate / 100), 2)
    add("loan_account", {
        "LOAN_ID": lid, "LOAN_ACCT_NUM": f"8{random.randint(10**7, 10**8 - 1)}",
        "LOAN_APP_ID": app, "LOAN_PARTY_ID": pid,
        "LOAN_PROD_CD": f"{ptype}-{random.randint(1, 3):02d}",
        "LOAN_PROD_TYPE_CD": ptype, "LOAN_CCY_CD": CCY,
        "LOAN_ORIG_AMT": orig, "LOAN_ORIG_DT": start,
        "LOAN_MATURITY_DT": d(start, term * 30, term * 30),
        "LOAN_TERM_MTHS": term, "LOAN_INT_RATE_PCT": rate,
        "LOAN_RATE_TYPE_CD": random.choices(
            ["FIXED", "VARIABLE", "TRACKER"], [0.55, 0.32, 0.13])[0],
        "LOAN_STATUS_CD": random.choices(
            ["ACTIVE", "CLOSED", "WRITTEN_OFF"], [0.9, 0.08, 0.02])[0],
        "LOAN_PRIN_BAL_AMT": prin,
        "LOAN_ACCR_INT_AMT": round(prin * rate / 1200, 2),
        "LOAN_INSTALMENT_AMT": inst, "LOAN_PAYMENT_FREQ_CD": "MTH",
        "LOAN_NEXT_DUE_DT": d(TODAY, 1, 31),
        "LOAN_DAYS_PAST_DUE": dpd, "LOAN_DELINQ_STAGE_CD": bucket,
        "LOAN_IMPAIRMENT_STAGE_CD": stage,
        "LOAN_ECL_AMT": round(prin * (0.004 if stage == "1" else
                                      0.06 if stage == "2" else 0.42), 2),
        "LOAN_BRANCH_CD": random.choice(BRANCHES),
        "LOAN_ORIG_CHANNEL_CD": random.choice(
            ["BRANCH", "WEB", "MOBILE", "BROKER"]),
    })
    n_sched = min(term, 18)
    for s in range(1, n_sched + 1):
        due = d(start, 30 * s, 30 * s)
        paid = due < TODAY and random.random() > 0.06
        p_amt = round(inst * random.uniform(0.55, 0.8), 2)
        add("repayment_schedule", {
            "SCHD_ID": f"S{lid[1:]}{s:03d}", "SCHD_LOAN_ID": lid,
            "SCHD_SEQ_NUM": s, "SCHD_DUE_DT": due, "SCHD_PRIN_AMT": p_amt,
            "SCHD_INT_AMT": round(inst - p_amt, 2), "SCHD_TOTAL_AMT": inst,
            "SCHD_PAID_FLG": paid,
            "SCHD_PAID_DT": d(due, -3, 6) if paid else "",
        })
    if ptype in ("MORT", "AUTO", "HELOC"):
        val = round(orig * random.uniform(1.15, 2.3), 2)
        add("collateral", {
            "COLL_ID": f"K{lid[1:]}", "COLL_LOAN_ID": lid,
            "COLL_TYPE_CD": "PROPERTY" if ptype in ("MORT", "HELOC")
                            else "VEHICLE",
            "COLL_DESC_TXT": (f"{random.randint(1, 240)} "
                              f"{random.choice(SURN)} Road, "
                              f"{random.choice(CITIES)}"
                              if ptype != "AUTO" else
                              f"Vehicle VIN {random.randint(10**9, 10**10 - 1)}"),
            "COLL_VALUE_AMT": val,
            "COLL_VALUATION_DT": d(start, -30, 20),
            "COLL_VALUATION_METHOD_CD": random.choices(
                ["FULL", "DESKTOP", "INDEXED"], [0.4, 0.35, 0.25])[0],
            "COLL_LTV_PCT": round(orig / val * 100, 4),
            "COLL_LIEN_POSITION_NUM": random.choices([1, 2], [0.9, 0.1])[0],
        })
for i in range(1, 91):
    limit = money(2000, 150000)
    appr = d(TODAY, -1500, -40)
    add("credit_facility", {
        "FAC_ID": f"F{i:06d}", "FAC_PARTY_ID": random.choice(PARTY_IDS),
        "FAC_TYPE_CD": random.choice(["REVOLVING", "TERM", "OVERDRAFT"]),
        "FAC_LIMIT_AMT": limit,
        "FAC_UTILISED_AMT": round(limit * random.uniform(0, 0.95), 2),
        "FAC_APPROVED_DT": appr, "FAC_EXPIRY_DT": d(appr, 365, 1460),
        "FAC_STATUS_CD": random.choices(
            ["ACTIVE", "SUSPENDED", "EXPIRED"], [0.87, 0.05, 0.08])[0],
    })

# ---------- TXN ----------
dep_owner = {r["DEP_ACCT_ID"]: r["DEP_PARTY_ID"] for r in rows["deposit_account"]}
loan_owner = {r["LOAN_ID"]: r["LOAN_PARTY_ID"] for r in rows["loan_account"]}
for i in range(1, N_TXN + 1):
    on_loan = random.random() < 0.34 and loan_ids
    if on_loan:
        acct = random.choice(loan_ids)
        owner, atype = loan_owner[acct], "LOAN"
        ttype = random.choices(["REPAYMENT", "INTEREST", "FEE"],
                               [0.78, 0.16, 0.06])[0]
        amt = money(60, 2600) * (-1 if ttype == "REPAYMENT" else 1)
    else:
        acct = random.choice(dep_ids)
        owner, atype = dep_owner[acct], "DEPOSIT"
        ttype = random.choices(["PAYMENT", "FEE", "INTEREST"],
                               [0.9, 0.06, 0.04])[0]
        amt = money(2, 3200) * random.choice([-1, -1, -1, 1])
    post = d(TODAY, -120, 0)
    rev = random.random() < 0.012
    add("transaction", {
        "TXN_ID": f"T{i:08d}", "TXN_ACCT_ID": acct, "TXN_ACCT_TYPE_CD": atype,
        "TXN_PARTY_ID": owner, "TXN_POST_DT": post,
        "TXN_VALUE_DT": d(post, 0, 2), "TXN_BOOKING_TS": ts(post, 0, 23),
        "TXN_AMT": amt, "TXN_CCY_CD": CCY,
        "TXN_DR_CR_IND": "D" if amt < 0 else "C",
        "TXN_TYPE_CD": ttype,
        "TXN_SUBTYPE_CD": random.choice(["STD", "SCHED", "ADHOC", "ADJ"]),
        "TXN_CHANNEL_CD": random.choices(
            ["MOBILE", "WEB", "BRANCH", "ATM", "SYSTEM"],
            [0.34, 0.24, 0.12, 0.1, 0.2])[0],
        "TXN_PAYMENT_METHOD_CD": random.choice(
            ["ACH", "WIRE", "CARD", "DD", "INTERNAL"]),
        "TXN_COUNTERPARTY_NAME": name() if random.random() < 0.6 else "",
        "TXN_COUNTERPARTY_ACCT_REF": f"CP{random.randint(10**6, 10**7 - 1)}",
        "TXN_MERCHANT_CATEGORY_CD": (f"{random.randint(4000, 7999)}"
                                     if random.random() < 0.4 else ""),
        "TXN_REF_NUM": f"E2E{random.randint(10**9, 10**10 - 1)}",
        "TXN_STATUS_CD": "REVERSED" if rev else
                         random.choices(["POSTED", "PENDING"], [0.97, 0.03])[0],
        "TXN_REVERSAL_FLG": rev,
        "TXN_ORIG_TXN_ID": f"T{random.randint(1, i):08d}" if rev else "",
        "TXN_BRANCH_CD": random.choice(BRANCHES),
    })

# ---------- BRN ----------
for b in BRANCHES:
    add("branch", {
        "BRN_BRANCH_CD": b, "BRN_BRANCH_NAME": f"{random.choice(CITIES)} Branch",
        "BRN_REGION_CD": random.choice(["NORTH", "SOUTH", "EAST", "WEST"]),
        "BRN_CITY_NAME": random.choice(CITIES), "BRN_COUNTRY_CD": "GB",
        "BRN_OPEN_DT": d(TODAY, -9000, -800),
        "BRN_STATUS_CD": random.choices(["OPEN", "CLOSED"], [0.94, 0.06])[0],
    })
branch_apps = [a for a in rows["loan_application"]
               if a["APP_CHANNEL_CD"] == "BRANCH"]
for i in range(1, N_VISIT + 1):
    linked = (random.choice(branch_apps)["APP_ID"]
              if branch_apps and random.random() < 0.22 else "")
    add("branch_visit", {
        "BRV_EVENT_ID": f"BV{i:06d}", "BRV_BRANCH_CD": random.choice(BRANCHES),
        "BRV_PARTY_ID": random.choice(PARTY_IDS),
        "BRV_TELLER_ID": f"U{random.randint(100, 399)}",
        "BRV_EVENT_TS": ts(d(TODAY, -180, 0), 9, 16),
        "BRV_EVENT_TYPE_CD": random.choices(
            ["TELLER", "ADVISORY", "ONBOARDING"], [0.6, 0.3, 0.1])[0],
        "BRV_SERVICE_CD": random.choice(
            ["CASH", "TRANSFER", "LOAN_ENQ", "ACCT_OPEN", "COMPLAINT"]),
        "BRV_QUEUE_WAIT_SEC": random.randint(0, 1500),
        "BRV_DURATION_SEC": random.randint(90, 2400),
        "BRV_OUTCOME_CD": random.choices(
            ["COMPLETED", "REFERRED", "ABANDONED"], [0.82, 0.13, 0.05])[0],
        "BRV_REFERRAL_PROD_CD": random.choice(["MORT", "PERS", "SAV", ""]),
        "BRV_APP_ID": linked,
    })

# ---------- DIG ----------
digital_apps = [a for a in rows["loan_application"]
                if a["APP_CHANNEL_CD"] in ("WEB", "MOBILE")]
ev = 0
for i in range(1, N_SESSION + 1):
    sid = f"SE{i:07d}"
    start_day = d(TODAY, -90, 0)
    start = ts(start_day, 6, 23)
    chan = random.choices(["MOBILE", "WEB"], [0.63, 0.37])[0]
    authres = random.choices(["SUCCESS", "FAIL", "LOCKED"], [0.94, 0.05, 0.01])[0]
    add("digital_session", {
        "SESS_ID": sid, "SESS_PARTY_ID": random.choice(PARTY_IDS),
        "SESS_CHANNEL_CD": chan,
        "SESS_DEVICE_TYPE_CD": ("PHONE" if chan == "MOBILE" else
                                random.choice(["DESKTOP", "TABLET"])),
        "SESS_OS_NAME": random.choice(["iOS", "Android", "Windows", "macOS"]),
        "SESS_START_TS": start,
        "SESS_END_TS": start + dt.timedelta(minutes=random.randint(1, 40)),
        "SESS_AUTH_METHOD_CD": random.choices(
            ["BIOMETRIC", "PWD", "MFA"], [0.5, 0.3, 0.2])[0],
        "SESS_AUTH_RESULT_CD": authres,
        "SESS_IP_ADDR": f"198.51.{random.randint(0, 255)}.{random.randint(1, 254)}",
    })
    if authres != "SUCCESS":
        continue
    journey = random.random() < 0.3 and digital_apps
    linked = random.choice(digital_apps)["APP_ID"] if journey else ""
    steps = (["PAGE_VIEW", "QUOTE", "APPLY_START", "APPLY_SUBMIT"] if journey
             else ["PAGE_VIEW"] * random.randint(1, 4))
    cut = len(steps) if not journey else random.randint(2, len(steps))
    for k, et in enumerate(steps[:cut]):
        ev += 1
        add("digital_event", {
            "EVT_ID": f"EV{ev:08d}", "EVT_SESS_ID": sid,
            "EVT_TS": start + dt.timedelta(seconds=45 * (k + 1)),
            "EVT_TYPE_CD": et,
            "EVT_PAGE_CD": random.choice(
                ["HOME", "PRODUCTS", "LOAN_CALC", "APPLY", "ACCOUNTS"]),
            "EVT_PROD_VIEWED_CD": random.choice(
                ["MORT", "PERS", "AUTO", "SAV", ""]),
            "EVT_APP_ID": linked if et.startswith("APPLY") else "",
            "EVT_ABANDON_FLG": journey and cut < len(steps) and k == cut - 1,
        })


# --------------------------------------------------------------------------
def entity_columns(entity: str) -> list[str]:
    for s in SYSTEMS.values():
        cols = [f[0] for f in s.fields if f[4] == entity]
        if cols:
            return cols
    raise KeyError(entity)


def system_of(entity: str) -> str:
    for code, s in SYSTEMS.items():
        if any(f[4] == entity for f in s.fields):
            return code
    raise KeyError(entity)


def main(outdir="."):
    os.makedirs(outdir, exist_ok=True)
    total = 0
    print(f"{BANK_CODE} synthetic extracts  (seed {SEED})")
    for entity, recs in rows.items():
        cols = entity_columns(entity)
        # the spec is the contract: any drift between generator and IDRA is a
        # bug, so fail loudly rather than writing a mismatched extract
        for r in recs:
            missing, extra = set(cols) - set(r), set(r) - set(cols)
            if missing or extra:
                raise AssertionError(
                    f"{entity}: missing={sorted(missing)} extra={sorted(extra)}")
        path = os.path.join(outdir, f"{system_of(entity)}_{entity}.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(recs)
        total += len(recs)
        print(f"  {system_of(entity)}  {entity:26} {len(recs):6,} rows  "
              f"{len(cols):2} cols")
    print(f"  {'':4}{'TOTAL':26} {total:6,} rows -> {os.path.abspath(outdir)}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "./bank_data")
