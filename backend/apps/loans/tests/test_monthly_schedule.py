"""BR-38: the society's monthly spreadsheet uploaded as it is kept (names and figures are made up)."""
import datetime
from decimal import Decimal

import pytest

from apps.ledger import services as ledger
from apps.ledger.models import Transaction
from apps.loans import services
from apps.loans.models import LoanProduct
from apps.loans.monthly_schedule import NameIndex, parse_cell
from apps.members.tests.helpers import xlsx_file
from tests.factories import MemberFactory, make_officer

pytestmark = pytest.mark.django_db
D = Decimal
BATCHES = "/api/v1/admin/batches/"
HEADER = ["S/N", "STAFF NAME", "CTSS EMDI", "TRANSFER TO ACCT", "REFUND", "PRE- RETIREMENT", "WITHDRAWAL FROM XMAS SAVINGS",
          "ELECTRONICS", "COMMODITY", "XMAS LOAN", "XMAS SAVINGS ", "COOP LOAN", "COOP SAVINGS", "TOTAL"]


def row(sn, name, ctss="", transfer="", refund="", pre="", withdrawal="", electronics="", commodity="", xmas_loan="",
        xmas="", coop_loan="", coop="", total=""):
    return [sn, name, ctss, transfer, refund, pre, withdrawal, electronics, commodity, xmas_loan, xmas, coop_loan, coop, total]


@pytest.fixture
def month(open_cycle):
    return datetime.date(open_cycle.year, 3, 1)


@pytest.fixture
def people(db, super_admin):
    """Adaeze Chioma Okafor with a running cooperative loan; Bola Ade Ige with none."""
    product = LoanProduct.objects.create(name="Cooperative Loan", code="COOPL", interest_rate=D("12"), interest_rate_basis="PER_LOAN",
                                         min_amount=D("1000"), max_amount=D("9000000"), min_term_months=1, max_term_months=18,
                                         guarantors_required=0)
    adaeze = MemberFactory(first_name="Adaeze", middle_name="Chioma", last_name="Okafor")
    bola = MemberFactory(first_name="Bola", middle_name="", last_name="Ige")
    loan = services.bring_forward_loan(super_admin, member=adaeze, product=product, outstanding=D("300000"), term_months=12,
                                       balance_date=datetime.date(2025, 12, 31))
    entry = Transaction.objects.get(loan=loan, txn_type="LOAN_OPENING_BALANCE")
    if entry.status == "PENDING":
        ledger.approve_entry(make_officer("Cooperative Chairman"), entry)
    loan.refresh_from_db()
    return {"adaeze": adaeze, "bola": bola, "loan": loan}


def upload(as_user, officer, rows, month):
    return as_user(officer).post(BATCHES, {"batch_type": "MONTHLY_SCHEDULE", "period": f"{month:%Y-%m}",
                                           "file": xlsx_file(HEADER, rows, name="jan.xlsx")}, format="multipart").data


def test_amounts_must_be_typed_clearly():
    assert parse_cell("120,000.00") == D("120000.00") and parse_cell(5000) == D("5000.00") and parse_cell(None) == D("0")
    for bad in ("100,00.00", "110,000,00", "1,280.000.00", "O"):
        with pytest.raises(ValueError):
            parse_cell(bad)


def test_names_are_matched_in_any_order(people):
    index = NameIndex()
    assert index.find("OKAFOR ADAEZE CHIOMA")[0] == people["adaeze"]
    assert index.find("IGE BOLA FUNMI")[0] == people["bola"]  # an extra name on payroll is fine
    assert index.find("NWOSU EMEKA")[0] is None


def test_the_sheet_becomes_contributions_and_repayments(as_user, treasurer, people, month):
    rows = [
        row(1, "OKAFOR ADAEZE CHIOMA", ctss=60000, transfer=20000, xmas=20000, coop_loan=50000, coop=10000, total=80000),
        row(2, "IGE BOLA", ctss=50000, refund=40000, coop=10000, total=10000),
        row(3, "TOTAL", ctss=110000, total=90000),
    ]
    batch = upload(as_user, treasurer, rows, month)
    assert batch["status"] == "VALIDATED", batch["validation_report"]
    entries = Transaction.objects.filter(batch_id=batch["id"])
    assert entries.count() == 4
    repayment = entries.get(loan=people["loan"])
    assert repayment.amount == D("50000.00") and repayment.channel == "MIXED" and repayment.period == month
    assert entries.get(member=people["bola"]).channel == "PAYROLL"

    chairman = make_officer("Cooperative Chairman")
    as_user(treasurer).post(f"{BATCHES}{batch['id']}/submit/")
    approved = as_user(chairman).post(f"{BATCHES}{batch['id']}/approve/").data
    assert approved.get("status") == "POSTED", approved
    assert -ledger.posted_balance(people["loan"]) == D("336000.00") - D("50000.00")  # 300,000 + 12% flat, less 50,000

    again = upload(as_user, treasurer, rows[:1], month)  # the same month cannot be taken twice
    assert again["status"] == "DRAFT" and again["validation_report"]["error_rows"] == 1


def test_problems_are_reported_row_by_row(as_user, treasurer, people, month):
    rows = [
        row(1, "OKAFOR ADAEZE CHIOMA", ctss=230000, xmas="100,00.00", coop_loan=120000, coop=10000, total=230000),
        row(2, "IGE BOLA", ctss=60000, coop_loan=50000, coop=10000, total=60000),
        row(3, "NWOSU EMEKA", ctss=20000, coop=20000, total=20000),
        row(4, "OKAFOR ADAEZE", transfer=900000, xmas=15000, coop=5000, total=920000),
    ]
    report = upload(as_user, treasurer, rows, month)["validation_report"]
    errors = {e["row"]: e["errors"] for e in report["errors"]}
    assert "xmas_savings" in errors[2]  # mistyped amount
    assert "no running coop loan" in errors[3]["coop_loan"][0]
    assert "No member called NWOSU EMEKA" in errors[4]["name"][0]
    assert any("shared out" in m for m in errors[5]["total"])  # 920,000 received, 20,000 shared out
    assert Transaction.objects.filter(batch__isnull=False).count() == 0  # nothing posted while any row is wrong


def test_a_row_with_nothing_paid_is_skipped(as_user, treasurer, people, month):
    batch = upload(as_user, treasurer, [row(1, "IGE BOLA", ctss=0), row(2, "IGE BOLA", ctss=5000, coop=5000, total=5000)], month)
    assert batch["status"] == "VALIDATED" and batch["line_count"] == 1


def test_withdrawals_from_christmas_savings_are_paid_out(as_user, treasurer, people, month, open_cycle):
    from apps.savings.models import SavingsAccount

    account = SavingsAccount.objects.get(member=people["bola"], cycle=open_cycle)
    Transaction.objects.create(member=people["bola"], txn_type="SAVINGS_CONTRIBUTION", entry_side="CREDIT", amount=D("50000"),
                               savings_account=account, period=datetime.date(open_cycle.year, 1, 1), status="POSTED",
                               posted_at=account.created_at)
    batch = upload(as_user, treasurer, [row(1, "IGE BOLA", ctss=5000, withdrawal=30000, coop=5000, total=5000)], month)
    assert batch["status"] == "VALIDATED", batch["validation_report"]
    withdrawal = Transaction.objects.get(batch_id=batch["id"], txn_type="SAVINGS_WITHDRAWAL")
    assert withdrawal.savings_account == account and withdrawal.amount == D("30000.00")

    too_much = upload(as_user, treasurer, [row(1, "IGE BOLA", withdrawal=90000)], datetime.date(open_cycle.year, 4, 1))
    assert "holds only" in too_much["validation_report"]["errors"][0]["errors"]["xmas_withdrawal"][0]
