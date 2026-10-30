"""
Load a demo cooperative: staff, members, savings, shares, loans in every state,
dues and ledger entries. Everything goes through the same services as the app,
so `python manage.py reconcile` passes on the result.

Dates are relative to today, so the demo always looks current. Local use only:
refuses to run unless DEBUG is on.

    python manage.py seed_demo            # first time
    python manage.py seed_demo --reset    # wipe the demo data and load it again
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.contributions import services as dues
from apps.contributions.models import Contribution
from apps.core.models import Notification, SystemSetting
from apps.finance import services as ledger
from apps.finance.models import LedgerEntry
from apps.loans import services as loans
from apps.loans.models import Loan, LoanProduct, LoanRepayment
from apps.members.models import Member
from apps.savings import services as savings
from apps.savings.models import SavingsAccount, SavingsTransaction
from apps.shares import services as shares
from apps.shares.models import ShareAccount, ShareTransaction

# Local demo accounts only (see README). Never used outside DEBUG.
DEMO_PASSWORD = "CoopManager-Demo-2026"
DEMO_DOMAIN = "coopmanager.local"

R = CustomUser.Role
STAFF = [
    # email name, first, last, role
    ("admin", "Amaka", "Eze", R.SUPER_ADMIN),
    ("manager", "Babatunde", "Adeyemi", R.MANAGER),
    ("accountant", "Funmi", "Okoro", R.ACCOUNTANT),
    ("loans", "Ibrahim", "Sani", R.LOAN_OFFICER),
]
MEMBERS = [
    # email name, first, last, phone, address
    ("chioma", "Chioma", "Nwankwo", "08031110001", "14 Aba Road, Port Harcourt"),
    ("yusuf", "Yusuf", "Bello", "08031110002", "3 Ahmadu Bello Way, Kaduna"),
    ("grace", "Grace", "Okon", "08031110003", "22 Marian Road, Calabar"),
    ("tunde", "Tunde", "Bakare", "08031110004", "9 Allen Avenue, Ikeja"),
    ("ngozi", "Ngozi", "Obi", "08031110005", "41 Ogui Road, Enugu"),
    ("aisha", "Aisha", "Lawal", "08031110006", "17 Zoo Road, Kano"),
    ("emeka", "Emeka", "Nwosu", "08031110007", "5 Wetheral Road, Owerri"),
    ("bisi", "Bisi", "Ade", "08031110008", "60 Ring Road, Ibadan"),
]
PRODUCTS = [
    ("Emergency Loan", "5.00", "200000.00", 6, "Quick support for urgent needs."),
    ("Asset Purchase Loan", "10.00", "1000000.00", 12, "Equipment, appliances and vehicles."),
    ("Business Loan", "12.00", "2000000.00", 18, "Working capital for members' businesses."),
]


class Command(BaseCommand):
    help = "Load a demo cooperative (local use only)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete existing demo data first.")

    def handle(self, *args, reset=False, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo only runs with DEBUG on. It creates accounts with a published password.")
        demo_users = CustomUser.objects.filter(email__endswith=f"@{DEMO_DOMAIN}")
        if demo_users.exists():
            if not reset:
                raise CommandError("Demo data is already loaded. Use --reset to load it again.")
            self._wipe(demo_users)

        self.now = timezone.now()
        with transaction.atomic():
            self._load()
        self.stdout.write(self.style.SUCCESS(
            f"Loaded {len(STAFF)} staff and {len(MEMBERS)} members. Sign in with any of "
            f"{', '.join(f'{e}@{DEMO_DOMAIN}' for e, *_ in STAFF + MEMBERS[:1])}, ... (password in seed_demo.py)."
        ))

    # ── helpers ─────────────────────────────────────────────────────────────
    def at(self, days_ago, minutes=0):
        """Run the next service call as if it happened `days_ago` days ago."""
        return mock.patch("django.utils.timezone.now",
                          return_value=self.now - timedelta(days=days_ago) + timedelta(minutes=minutes))

    def _wipe(self, demo_users):
        with transaction.atomic():
            members = Member.objects.filter(user__in=demo_users)
            LedgerEntry.objects.filter(reverses__isnull=False).delete()
            LedgerEntry.objects.all().delete()
            LoanRepayment.objects.filter(loan__member__in=members).delete()
            Loan.objects.filter(member__in=members).delete()
            LoanProduct.objects.filter(name__in=[p[0] for p in PRODUCTS]).delete()
            Contribution.objects.filter(member__in=members).delete()
            ShareTransaction.objects.filter(account__member__in=members).delete()
            ShareAccount.objects.filter(member__in=members).delete()
            SavingsTransaction.objects.filter(account__member__in=members).delete()
            SavingsAccount.objects.filter(member__in=members).delete()
            Notification.objects.filter(user__in=demo_users).delete()
            SystemSetting.objects.all().delete()
            demo_users.delete()

    def _user(self, email, first, last, role, phone=None, address=""):
        user = CustomUser(email=f"{email}@{DEMO_DOMAIN}", first_name=first, last_name=last, role=role,
                          is_staff=role in (R.SUPER_ADMIN, R.MANAGER), is_superuser=role == R.SUPER_ADMIN)
        user.set_password(DEMO_PASSWORD)
        user.save()
        Member.objects.filter(user=user).update(
            first_name=first, last_name=last, status=Member.Status.ACTIVE,
            residential_address=address or "Cooperative office", **({"phone_number": phone} if phone else {}),
        )
        return user

    # ── the story ───────────────────────────────────────────────────────────
    def _load(self):
        SystemSetting.objects.create(cooperative_name="Unity Staff Multipurpose Cooperative",
                                     registration_number="COOP-DEMO-001", share_unit_price=Decimal("1000.00"))
        staff = {e: self._user(e, f, l, r) for e, f, l, r in STAFF}
        acct, officer, manager = staff["accountant"], staff["loans"], staff["manager"]
        members = {e: self._user(e, f, l, R.MEMBER, phone=p, address=a) for e, f, l, p, a in MEMBERS}
        products = {name: LoanProduct.objects.create(name=name, interest_rate=Decimal(rate), max_amount=Decimal(cap),
                                                     max_duration_months=months, description=desc)
                    for name, rate, cap, months, desc in PRODUCTS}
        profile = {e: u.member_profile for e, u in members.items()}
        account = {e: SavingsAccount.objects.get(member=p) for e, p in profile.items()}

        # Monthly savings over the last five months.
        monthly = {"chioma": 25000, "yusuf": 40000, "grace": 15000, "tunde": 30000,
                   "ngozi": 20000, "aisha": 35000, "emeka": 10000, "bisi": 18000}
        for month in range(5, 0, -1):
            for i, (email, amount) in enumerate(monthly.items()):
                with self.at(month * 30, minutes=i):
                    savings.record(account=account[email], txn_type="DEPOSIT", amount=amount, by=acct,
                                   description="Monthly savings")
        with self.at(40):
            savings.record(account=account["tunde"], txn_type="WITHDRAWAL", amount=20000, by=acct,
                           description="School fees")

        # Requests waiting in the Approvals queue.
        with self.at(1):
            savings.record(account=account["grace"], txn_type="WITHDRAWAL", amount=12000, by=members["grace"],
                           description="Medical bill")
        with self.at(0, minutes=-90):
            savings.record(account=account["emeka"], txn_type="DEPOSIT", amount=50000, by=members["emeka"],
                           description="Transfer from salary account")

        # Share capital: staff-recorded purchases, plus one member request pending.
        for i, (email, n) in enumerate({"chioma": 50, "yusuf": 120, "aisha": 80, "ngozi": 30}.items()):
            with self.at(120 - i):
                shares.purchase(member=profile[email], number_of_shares=n, by=acct)
        with self.at(2):
            shares.purchase(member=profile["bisi"], number_of_shares=25, by=members["bisi"])

        # Loans in every state.
        def lifecycle(email, product, amount, months, purpose, applied, approved=None, disbursed=None, repaid=()):
            with self.at(applied):
                loan = loans.apply(member=profile[email], product=products[product], principal=amount,
                                   months=months, purpose=purpose, by=members[email])
            Loan.objects.filter(pk=loan.pk).update(application_date=(self.now - timedelta(days=applied)).date())
            if approved is not None:
                with self.at(approved):
                    loans.approve(loan, by=officer)
            if disbursed is not None:
                with self.at(disbursed):
                    loans.disburse(loan, by=manager)
            for days_ago, paid in repaid:
                with self.at(days_ago):
                    rep = loans.repay(loan, amount=paid, by=acct)
                LoanRepayment.objects.filter(pk=rep.pk).update(payment_date=(self.now - timedelta(days=days_ago)).date())
            return loan

        lifecycle("yusuf", "Business Loan", 500000, 12, "Restocking the provisions shop",
                  applied=100, approved=97, disbursed=95, repaid=[(65, 46667), (35, 46667), (5, 46667)])
        lifecycle("chioma", "Emergency Loan", 80000, 4, "Hospital bill",
                  applied=150, approved=149, disbursed=148, repaid=[(118, 21000), (88, 21000), (58, 21000), (28, 21000)])
        lifecycle("aisha", "Asset Purchase Loan", 350000, 10, "Deep freezer for the business",
                  applied=6, approved=4)
        lifecycle("tunde", "Business Loan", 1200000, 18, "Second-hand bus for transport business", applied=2)
        lifecycle("emeka", "Emergency Loan", 60000, 3, "Rent", applied=3)
        rejected = lifecycle("ngozi", "Asset Purchase Loan", 900000, 12, "Car purchase", applied=20)
        with self.at(18):
            loans.reject(rejected, by=officer, reason="Exceeds 3× savings; reapply after six more months of savings.")

        # Dues and a fine.
        for i, email in enumerate(MEMBERS):
            with self.at(32, minutes=i):
                due = dues.assess(member=profile[email[0]], type="MONTHLY_DUES", amount=Decimal("2000"),
                                  due_date=(self.now - timedelta(days=2)).date(), by=acct)
            if email[0] not in ("emeka", "bisi"):
                with self.at(10, minutes=i):
                    dues.mark_paid(due, by=acct)
        with self.at(12):
            dues.assess(member=profile["emeka"], type="FINE", amount=Decimal("1500"),
                        due_date=(self.now + timedelta(days=14)).date(), by=acct)

        # Running costs, and one corrected mistake.
        for days_ago, category, amount, note in [
            (60, "Office Rent", 150000, "Quarterly office rent"),
            (30, "Stationery", 18500, "Ledgers, receipt books and printer toner"),
            (15, "Bank Charges", 3200, "Monthly account maintenance"),
        ]:
            with self.at(days_ago):
                ledger.record(type="EXPENSE", category=category, amount=amount, description=note, recorded_by=acct)
        with self.at(9):
            mistake = ledger.record(type="EXPENSE", category="Stationery", amount=18500,
                                    description="Ledgers and toner (entered twice by mistake)", recorded_by=acct)
        with self.at(8):
            ledger.reverse(mistake, by=manager, reason="Duplicate of the stationery entry")
