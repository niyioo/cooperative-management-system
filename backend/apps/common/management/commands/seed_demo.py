"""
Load demonstration data for local development and training.

    python manage.py seed_demo

Creates the three officials and support staff, members, two Christmas savers who are
not members, EMDI's four loans (Cooperative, Commodity, Electronics, Christmas), monthly
Regular Savings contributions (with some arrears), Pre-retirement Savings, a Christmas
Savings cycle with monthly contributions and a withdrawal, a running Cooperative Loan
with two guarantors, investments and a published dividend for last year, all through the
normal services so every rule and audit entry applies.

Demo sign-ins (all share DEMO_PASSWORD below; change them if the database is
reachable by anyone else):
    admin@demo.emdi.test       Super Administrator
    treasurer@demo.emdi.test   Treasurer
    chairman@demo.emdi.test    Cooperative Chairman
    secretary@demo.emdi.test   Cooperative Secretary
    accountant@demo.emdi.test  Accountant
    ada@demo.emdi.test         Member (Ada Okafor) — also sign in with her membership number
    bayo@demo.emdi.test        Member (Bayo Adeyemi)

Refuses to run unless DEBUG is on, or --allow-production is given.
"""
import datetime
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.configuration.models import CooperativeSettings, Department
from apps.dividends import services as dividends
from apps.investments import services as investments
from apps.investments.models import InvestmentAccount, InvestmentProduct
from apps.ledger import services as ledger
from apps.ledger.models import Transaction
from apps.loans import services as loans
from apps.loans.models import LoanProduct
from apps.members.models import Member
from apps.members.services import create_member_record
from apps.notifications.models import Announcement
from apps.savings import services as savings
from apps.savings import statutory
from apps.savings.models import MonthlyContributionChange, SavingsAccount, SavingsCycle, SavingsProduct

DEMO_PASSWORD = "Emdi-Demo-2026"
D = Decimal


class Command(BaseCommand):
    help = "Load demonstration data (development only)."

    def add_arguments(self, parser):
        parser.add_argument("--allow-production", action="store_true", help="Run even when DEBUG is off.")

    def handle(self, *args, allow_production=False, **options):
        if not settings.DEBUG and not allow_production:
            raise CommandError("seed_demo only runs with DEBUG on. Use --allow-production if you really mean it.")
        if User.objects.filter(email="admin@demo.emdi.test").exists():
            self.stdout.write(self.style.WARNING("Demo data is already loaded."))
            return
        with transaction.atomic():
            self._seed()
        self.stdout.write(self.style.SUCCESS(f"Demo data loaded. Password for every demo account: {DEMO_PASSWORD}"))

    # ------------------------------------------------------------------

    def _officer(self, email, first, last, role, superuser=False):
        user = User.objects.create_user(email=email, password=DEMO_PASSWORD, first_name=first, last_name=last, is_staff_officer=True)
        if superuser:
            user.is_superuser = user.is_staff = True
            user.save()
        user.groups.add(Group.objects.get(name=role))
        return user

    def _member(self, admin, email, first, last, dept, joined, staff):
        member = create_member_record(
            admin,
            email=email,
            status=Member.Status.ACTIVE,
            profile={"first_name": first, "last_name": last, "phone": f"0803{staff[-4:]}000", "department": dept,
                     "date_joined": joined, "staff_number": staff, "designation": "Engineer", "grade_level": "GL 10",
                     "title": "ENGR", "residential_address": "EMDI Staff Quarters, Akure"},
            next_of_kin={"full_name": f"{last} Family", "relationship": "Spouse", "phone": "08030000000"},
        )
        member.user.set_password(DEMO_PASSWORD)
        member.user.save()
        return member

    def _seed(self):
        today = timezone.localdate()
        year = today.year
        coop = CooperativeSettings.load()
        coop.registration_number = "OD/COOP/1999/0421"
        coop.address = "Engineering Materials Development Institute, Ondo Road, Akure, Ondo State"
        coop.save()

        admin = self._officer("admin@demo.emdi.test", "Funmi", "Adewale", "Super Administrator", superuser=True)
        treasurer = self._officer("treasurer@demo.emdi.test", "Kunle", "Bakare", "Treasurer")
        chairman = self._officer("chairman@demo.emdi.test", "Emeka", "Nwosu", "Cooperative Chairman")
        secretary = self._officer("secretary@demo.emdi.test", "Halima", "Usman", "Cooperative Secretary")
        accountant = self._officer("accountant@demo.emdi.test", "Tolu", "Ajayi", "Accountant")

        metallurgy = Department.objects.create(name="Metallurgical Engineering", code="MET")
        Department.objects.create(name="Ceramics and Glass", code="CER")
        Department.objects.create(name="Polymers and Composites", code="POL")

        ada = self._member(admin, "ada@demo.emdi.test", "Ada", "Okafor", metallurgy, datetime.date(year - 6, 3, 1), "EMDI/0421")
        bayo = self._member(admin, "bayo@demo.emdi.test", "Bayo", "Adeyemi", metallurgy, datetime.date(year - 3, 9, 1), "EMDI/0533")
        others = [
            self._member(admin, f"member{i}@demo.emdi.test", first, last, metallurgy, datetime.date(year - 2, 1, 1), f"EMDI/07{i:02d}")
            for i, (first, last) in enumerate([("Chidi", "Obi"), ("Zainab", "Bello"), ("Tunde", "Ogun")], start=1)
        ]
        everyone = [ada, bayo, *others]
        # Monthly take-home pay, so officers can see whether repayments fit (BR-37).
        for member, pay in zip(everyone, ("320000", "240000", "210000", "260000", "190000")):
            Member.objects.filter(pk=member.pk).update(monthly_net_pay=D(pay))
        # Christmas savers (BR-33): staff who are not members but save in Christmas Savings through payroll.
        savers = [
            create_member_record(
                admin, status=Member.Status.ACTIVE, membership_type=Member.Type.CHRISTMAS_SAVER, reason="Registered as a Christmas saver",
                profile={"first_name": first, "last_name": last, "phone": phone, "department": metallurgy, "staff_number": staff,
                         "date_joined": datetime.date(year, 1, 5), "designation": "Technologist"},
            )
            for first, last, phone, staff in [("Grace", "Danjuma", "08034440001", "EMDI/0801"), ("Musa", "Ibrahim", "08034440002", "EMDI/0802")]
        ]

        # Savings: regular opening balances, then Christmas Savings for this year.
        regular = SavingsProduct.objects.get(code="REGULAR")
        christmas = SavingsProduct.objects.get(code="CHRISTMAS")
        for member, amount in zip(everyone, ("185000", "92000", "110000", "75500", "40000")):
            account = SavingsAccount.objects.get(member=member, product=regular)
            Transaction.objects.create(member=member, txn_type="SAVINGS_OPENING_BALANCE", entry_side="CREDIT", amount=D(amount),
                                       savings_account=account, value_date=datetime.date(year, 1, 2), status="POSTED",
                                       posted_at=timezone.now(), created_by=accountant, approved_by=treasurer,
                                       description="Regular Savings balance brought forward")
        cycle = savings.create_cycle(treasurer, product=christmas, year=year, expected_monthly_contribution=D("5000"))
        savings.open_cycle(treasurer, cycle)
        last_month = min(today.month, 10)
        for member in everyone + savers:
            account = SavingsAccount.objects.get(member=member, cycle=cycle)
            for month in range(1, last_month + 1):
                if member == bayo and month in (4, 5):
                    continue  # Bayo missed two months
                if member == savers[1] and month < 6:
                    continue  # Musa started saving in June
                savings.post_contribution(accountant, account=account, amount=D("5000"), period=datetime.date(year, month, 1),
                                          value_date=min(datetime.date(year, month, 25), today), description=f"Payroll deduction {datetime.date(year, month, 1):%b %Y}")

        # Monthly statutory contributions into Regular Savings (BR-29), ₦5,000 minimum and no
        # maximum (the product defaults). The system "went live" in January, when the opening
        # balances above were brought forward, so the accounts open then and arrears count from
        # there. Ada chose ₦10,000; Bayo missed April and May and Tunde missed June, so both are
        # in arrears. Zainab has asked for ₦8,000 from next month.
        SavingsAccount.objects.filter(member__in=everyone, product=regular).update(opened_on=datetime.date(year, 1, 1))
        ada_regular = SavingsAccount.objects.get(member=ada, product=regular)
        MonthlyContributionChange.objects.create(account=ada_regular, amount=D("10000"), effective_from=datetime.date(year, 1, 1),
                                                 changed_by=ada.user, reason="Chosen by the member")
        SavingsAccount.objects.filter(pk=ada_regular.pk).update(elected_monthly_amount=D("10000"))
        tunde = others[2]
        for member in everyone:
            account = SavingsAccount.objects.get(member=member, product=regular)
            for month in range(1, today.month):
                if (member == bayo and month in (4, 5)) or (member == tunde and month == 6):
                    continue
                period = datetime.date(year, month, 1)
                savings.post_contribution(accountant, account=account, amount=D("10000") if member == ada else D("5000"), period=period,
                                          value_date=datetime.date(year, month, 25), description=f"Payroll deduction {period:%b %Y}",
                                          external_reference=f"PAYROLL-{period:%Y-%m}")
        # Grace took ₦10,000 out of her Christmas Savings in July (BR-40); the payout is what is left.
        grace_christmas = SavingsAccount.objects.get(member=savers[0], cycle=cycle)
        withdrawal = savings.post_withdrawal(treasurer, account=grace_christmas, amount=D("10000"),
                                             reason="Hospital bill", value_date=min(datetime.date(year, 7, 14), today))
        ledger.approve_entry(chairman, withdrawal)

        # Pre-retirement Savings (BR-37): optional, kept until the member retires.
        pre_retirement = SavingsProduct.objects.get(code="PRE_RETIREMENT")
        ada_retirement = SavingsAccount.objects.create(member=ada, product=pre_retirement, opened_on=datetime.date(year, 1, 1))
        Transaction.objects.create(member=ada, txn_type="SAVINGS_OPENING_BALANCE", entry_side="CREDIT", amount=D("60000"),
                                   savings_account=ada_retirement, value_date=datetime.date(year, 1, 2), status="POSTED",
                                   posted_at=timezone.now(), created_by=accountant, approved_by=treasurer,
                                   description="Pre-retirement Savings balance brought forward")

        zainab = others[1]
        statutory.set_monthly_contribution(zainab.user, SavingsAccount.objects.get(member=zainab, product=regular),
                                           amount=D("8000"), by_member=True)

        # EMDI's loans (BR-37): interest charged once on the amount borrowed; all but the
        # Cooperative Loan must be repaid by October.
        once = dict(interest_rate_basis="PER_LOAN", interest_method="FLAT", interest_collection="AMORTISED",
                    min_amount=D("10000"), min_term_months=1, max_active_loans=1)
        product = LoanProduct.objects.create(
            name="Cooperative Loan", code="REG", **once, interest_rate=D("12"), max_amount=D("50000000"), max_term_months=18,
            max_savings_multiple=D("3"), official_savings_multiple=D("4"), guarantors_required=2, min_membership_months=6,
            description="Cash loan: 12% once, up to 18 months, three times Regular Savings (four times for officials). "
                        "Two guarantors.",
        )
        LoanProduct.objects.create(
            name="Commodity Loan", code="COM", loan_type="COMMODITY", **once, interest_rate=D("10"), max_amount=D("200000"),
            max_term_months=3, must_end_by_month=10, guarantors_required=0,
            description="Goods on credit: 10% once, up to 3 months and ₦200,000, repaid by October.",
        )
        LoanProduct.objects.create(
            name="Electronics Loan", code="ELE", loan_type="ELECTRONICS", **once, interest_rate=D("15"), max_amount=D("500000"),
            max_term_months=6, must_end_by_month=10, guarantors_required=0,
            description="Electronics on credit: 15% once, up to 6 months and ₦500,000, repaid by October.",
        )
        LoanProduct.objects.create(
            name="Christmas Loan", code="XMAS", loan_type="CHRISTMAS", **once, interest_rate=D("20"), max_amount=D("50000000"),
            max_term_months=6, must_end_by_month=10, guarantors_required=0, open_to_non_members=True,
            description="From the Christmas Savings Fund: 20% once, up to 6 months, repaid by October; members and "
                        "Christmas savers.",
        )

        # A running Cooperative Loan for Ada (paid out in March, repaid monthly since): Chidi and
        # Zainab guarantee it, the Secretary collated it and the Chairman approved it.
        application = loans.create_application(secretary, member=ada, product=product, amount_requested=D("240000"),
                                               term_months=12, purpose="Roofing repairs")
        guarantees = [loans.add_guarantor(secretary, application, m.membership_number) for m in (others[0], others[1])]
        loans.submit_application(secretary, application)
        for guarantee, guarantor in zip(guarantees, (others[0], others[1])):
            loans.respond_to_guarantee(guarantor.user, guarantee, accept=True)
        loans.start_review(secretary, application)
        loans.approve_application(chairman, application)
        disbursed_on = datetime.date(year, 3, 10) if today >= datetime.date(year, 3, 10) else today
        loan = loans.disburse(treasurer, application, disbursed_on=disbursed_on)
        ledger.approve_entry(chairman, Transaction.objects.get(loan=loan, txn_type="LOAN_DISBURSEMENT"))
        for instalment in loan.installments.filter(due_date__lt=today):
            loans.record_repayment(accountant, loan, amount=instalment.principal_due + instalment.interest_due,
                                   value_date=instalment.due_date, description="Payroll deduction")

        # Investments, contributed last year, and last year's published dividend.
        shares = InvestmentProduct.objects.create(name="Share Capital", code="SHARES", min_amount=D("1000"),
                                                  description="Members' share capital; earns the annual dividend.")
        for member, amount in zip(everyone, ("150000", "80000", "50000", "60000", "25000")):
            account = InvestmentAccount.objects.create(member=member, product=shares)
            Transaction.objects.create(member=member, txn_type="INVESTMENT_CONTRIBUTION", entry_side="CREDIT", amount=D(amount),
                                       investment_account=account, value_date=datetime.date(year - 1, 1, 15), status="POSTED",
                                       posted_at=timezone.now(), created_by=accountant, approved_by=treasurer,
                                       description="Share capital")
        investments.record_return(accountant, product=shares, financial_year=year - 1, amount_earned=D("4200000"),
                                  description="Returns on fixed deposits and equipment leasing")
        cycle_last_year = dividends.create_cycle(accountant, financial_year=year - 1, rate=D("12.5"))
        dividends.calculate(accountant, cycle_last_year)
        dividends.approve(chairman, cycle_last_year)
        dividends.publish(chairman, cycle_last_year)

        Announcement.objects.create(
            title="Annual General Meeting — 12 December",
            body="All members are invited to the AGM at the EMDI auditorium, 10:00 am. Dividends for the year will be announced.",
            is_important=True, publish_at=timezone.now(), created_by=admin,
        )
        Announcement.objects.create(
            title="Christmas Savings payout in November",
            body="Christmas Savings close at the end of October and are paid into members' bank accounts in November.",
            publish_at=timezone.now(), created_by=admin,
        )
        # Member notifications (loan approved and disbursed, dividend published) are created
        # by the services above, exactly as in real use.
