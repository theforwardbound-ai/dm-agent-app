"""Referential integrity gate for the Northbeam Bank synthetic extracts.

The extracts are only useful as modelling input if the cross-system keys
actually resolve — a model derived from them gets validated by running the
generated ETL, and that only means something if the joins hold.

    python scripts/check_bank_data.py [datadir]
"""
import csv
import os
import sys


def load(datadir, fname):
    with open(os.path.join(datadir, fname), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def ids(rows, key):
    return {r[key] for r in rows if r.get(key)}


def main(datadir="./bank_data"):
    party_rows = load(datadir, "CMD_party.csv")
    dep_rows = load(datadir, "DEP_deposit_account.csv")
    app_rows = load(datadir, "LND_loan_application.csv")
    loan_rows = load(datadir, "LND_loan_account.csv")
    txn_rows = load(datadir, "TXN_transaction.csv")
    visit_rows = load(datadir, "BRN_branch_visit.csv")
    branch_rows = load(datadir, "BRN_branch.csv")

    party = ids(party_rows, "PARTY_ID")
    dep = ids(dep_rows, "DEP_ACCT_ID")
    app = ids(app_rows, "APP_ID")
    loan = ids(loan_rows, "LOAN_ID")
    branch = ids(branch_rows, "BRN_BRANCH_CD")

    checks = [
        ("loan.PARTY -> party", ids(loan_rows, "LOAN_PARTY_ID") - party),
        ("loan.APP -> application", ids(loan_rows, "LOAN_APP_ID") - app),
        ("loan.BRANCH -> branch", ids(loan_rows, "LOAN_BRANCH_CD") - branch),
        ("application.PARTY -> party", ids(app_rows, "APP_PARTY_ID") - party),
        ("schedule.LOAN -> loan",
         ids(load(datadir, "LND_repayment_schedule.csv"), "SCHD_LOAN_ID") - loan),
        ("collateral.LOAN -> loan",
         ids(load(datadir, "LND_collateral.csv"), "COLL_LOAN_ID") - loan),
        ("facility.PARTY -> party",
         ids(load(datadir, "LND_credit_facility.csv"), "FAC_PARTY_ID") - party),
        ("deposit.PARTY -> party", ids(dep_rows, "DEP_PARTY_ID") - party),
        ("balance_hist.ACCT -> deposit",
         ids(load(datadir, "DEP_deposit_balance_history.csv"),
             "DEPH_ACCT_ID") - dep),
        ("visit.PARTY -> party", ids(visit_rows, "BRV_PARTY_ID") - party),
        ("visit.APP -> application", ids(visit_rows, "BRV_APP_ID") - app),
        ("visit.BRANCH -> branch", ids(visit_rows, "BRV_BRANCH_CD") - branch),
        ("session.PARTY -> party",
         ids(load(datadir, "DIG_digital_session.csv"), "SESS_PARTY_ID") - party),
        ("event.APP -> application",
         ids(load(datadir, "DIG_digital_event.csv"), "EVT_APP_ID") - app),
        ("txn.PARTY -> party", ids(txn_rows, "TXN_PARTY_ID") - party),
    ]

    orphan_txn = {r["TXN_ACCT_ID"] for r in txn_rows
                  if (r["TXN_ACCT_TYPE_CD"] == "LOAN"
                      and r["TXN_ACCT_ID"] not in loan)
                  or (r["TXN_ACCT_TYPE_CD"] == "DEPOSIT"
                      and r["TXN_ACCT_ID"] not in dep)}
    checks.append(("txn.ACCT -> deposit|loan", orphan_txn))

    # every drawn loan must trace to an APPROVED application
    approved = {r["APP_ID"] for r in app_rows if r["APP_DECISION_CD"] == "APPROVE"}
    checks.append(("loan traces to APPROVED app",
                   ids(loan_rows, "LOAN_APP_ID") - approved))

    bad = 0
    for label, orphans in checks:
        flag = "OK  " if not orphans else "FAIL"
        print(f"  {flag} {label:32} orphans={len(orphans)}")
        bad += len(orphans)
    print("REFERENTIAL INTEGRITY:", "PASS" if bad == 0 else f"FAIL ({bad})")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "./bank_data"))
