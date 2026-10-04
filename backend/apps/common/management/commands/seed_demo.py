"""
Load demonstration data for local development and training.

    python manage.py seed_demo

Creates officers, members, products, monthly Regular Savings contributions (with
some arrears), a Christmas Savings cycle with monthly contributions, a running loan, investments and a published dividend for last
year, all through the normal services so every rule and audit entry applies.

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
        self._officer("secretary@demo.emdi.test", "Halima", "Usman", "Cooperative Secretary")
        accountant = self._officer("accountant@demo.emdi.test", "Tolu", "Ajayi", "Accountant")
        loan_officer = self._officer("loans@demo.emdi.test", "Ngozi", "Eze", "Loan Officer")

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

        # Savings: regular opening balances, then Christmas Savings for this year.
        regular = SavingsProduct.objects.get(code="REGULAR")
        christmas = SavingsProduct.objects.get(code="CHRISTMAS")
        for member, amount in zip(everyone, ("185000", "92000", "60000", "75500", "40000")):
            account = SavingsAccount.objects.get(member=member, product=regular)
            Transaction.objects.create(member=member, txn_type="SAVINGS_OPENING_BALANCE", entry_side="CREDIT", amount=D(amount),
                                       savings_account=account, value_date=datetime.date(year, 1, 2), status="POSTED",
                                       posted_at=timezone.now(), created_by=accountant, approved_by=treasurer,
                                       description="Regular Savings balance brought forward")
        cycle = savings.create_cycle(treasurer, product=christmas, year=year, expected_monthly_contribution=D("5000"))
        savings.open_cycle(treasurer, cycle)
        last_month = min(today.month, 10)
        for member in everyone:
            account = SavingsAccount.objects.get(member=member, cycle=cycle)
            for month in range(1, last_month + 1):
                if member == bayo and month in (4, 5):
                    continue  # Bayo missed two months
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
        zainab = others[1]
        statutory.set_monthly_contribution(zainab.user, SavingsAccount.objects.get(member=zainab, product=regular),
                                           amount=D("8000"), by_member=True)

        # A running loan for Ada (disbursed in March, repaid monthly since).
        product = LoanProduct.objects.create(
            name="Regular Loan", code="REG", description="General purpose loan repaid through payroll.",
            interest_rate=D("10"), min_amount=D("20000"), max_amount=D("2000000"), max_savings_multiple=D("2"),
            min_term_months=3, max_term_months=24, min_membership_months=6,
            required_documents=["Latest payslip"],
        )
        LoanProduct.objects.create(
            name="Emergency Loan", code="EMG", description="Quick small loan, interest deducted upfront.",
            interest_rate=D("5"), interest_rate_basis="PER_LOAN", interest_collection="UPFRONT",
            min_amount=D("10000"), max_amount=D("150000"), min_term_months=1, max_term_months=6, min_membership_months=3,
        )
        application = loans.create_application(loan_officer, member=ada, product=product, amount_requested=D("240000"),
                                               term_months=12, purpose="Roofing repairs")
        guarantee = loans.add_guarantor(loan_officer, application, others[0].membership_number)  # Chidi
        loans.submit_application(loan_officer, application)
        loans.respond_to_guarantee(others[0].user, guarantee, accept=True)
        loans.start_review(loan_officer, application)
        loans.approve_application(chairman, application)
        disbursed_on = datetime.date(year, 3, 10) if today >= datetime.date(year, 3, 10) else today
        loan = loans.disburse(treasurer, application, disbursed_on=disbursed_on)
        ledger.approve_entry(chairman, Transaction.objects.get(loan=loan, txn_type="LOAN_DISBURSEMENT"))
        for instalment in loan.installments.filter(due_date__lt=today):
            loans.record_repayment(accountant, loan, amount=instalment.principal_due + instalment.interest_due,
                                   value_date=instalment.due_date, description="Payroll deduction")

        # Bayo has an application waiting for review, with Ada asked to guarantee it.
        pending = loans.create_application(bayo.user, member=bayo, product=product, amount_requested=D("150000"),
                                           term_months=10, purpose="School fees")
        loans.add_guarantor(bayo.user, pending, ada.membership_number)  # Ada is asked; her answer is pending
        loans.submit_application(bayo.user, pending)

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
