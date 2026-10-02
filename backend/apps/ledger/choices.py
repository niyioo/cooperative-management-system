"""
Ledger vocabulary. Kept free of model imports so any app (including
configuration) can import it without creating import cycles.
"""
from django.db import models


class TransactionType(models.TextChoices):
    SAVINGS_OPENING_BALANCE = "SAVINGS_OPENING_BALANCE", "Savings opening balance"
    SAVINGS_CONTRIBUTION = "SAVINGS_CONTRIBUTION", "Savings contribution"
    SAVINGS_WITHDRAWAL = "SAVINGS_WITHDRAWAL", "Savings withdrawal"
    SAVINGS_CYCLE_PAYOUT = "SAVINGS_CYCLE_PAYOUT", "Savings cycle payout"
    LOAN_DISBURSEMENT = "LOAN_DISBURSEMENT", "Loan disbursement"
    LOAN_INTEREST_CHARGE = "LOAN_INTEREST_CHARGE", "Loan interest charge"
    LOAN_PENALTY = "LOAN_PENALTY", "Loan penalty"
    LOAN_REPAYMENT = "LOAN_REPAYMENT", "Loan repayment"
    INVESTMENT_OPENING_BALANCE = "INVESTMENT_OPENING_BALANCE", "Investment opening balance"
    INVESTMENT_CONTRIBUTION = "INVESTMENT_CONTRIBUTION", "Investment contribution"
    INVESTMENT_LIQUIDATION = "INVESTMENT_LIQUIDATION", "Investment liquidation"
    DIVIDEND_PAYMENT = "DIVIDEND_PAYMENT", "Dividend payment"
    ADJUSTMENT = "ADJUSTMENT", "Adjustment"
    REVERSAL = "REVERSAL", "Reversal"


class EntrySide(models.TextChoices):
    """
    Side from the account's point of view.
    Savings/investment balance = credits - debits.
    Loan outstanding = debits - credits.
    """

    CREDIT = "CREDIT", "Credit"
    DEBIT = "DEBIT", "Debit"


class TransactionStatus(models.TextChoices):
    PENDING = "PENDING", "Pending approval"
    POSTED = "POSTED", "Posted"
    REJECTED = "REJECTED", "Rejected"
    REVERSED = "REVERSED", "Reversed"


class AccountKind(models.TextChoices):
    SAVINGS = "SAVINGS", "Savings"
    LOAN = "LOAN", "Loan"
    INVESTMENT = "INVESTMENT", "Investment"


T = TransactionType

# Which account each type must post to, and on which side. None = decided per entry.
TYPE_RULES = {
    T.SAVINGS_OPENING_BALANCE: (AccountKind.SAVINGS, EntrySide.CREDIT),
    T.SAVINGS_CONTRIBUTION: (AccountKind.SAVINGS, EntrySide.CREDIT),
    T.SAVINGS_WITHDRAWAL: (AccountKind.SAVINGS, EntrySide.DEBIT),
    T.SAVINGS_CYCLE_PAYOUT: (AccountKind.SAVINGS, EntrySide.DEBIT),
    T.LOAN_DISBURSEMENT: (AccountKind.LOAN, EntrySide.DEBIT),
    T.LOAN_INTEREST_CHARGE: (AccountKind.LOAN, EntrySide.DEBIT),
    T.LOAN_PENALTY: (AccountKind.LOAN, EntrySide.DEBIT),
    T.LOAN_REPAYMENT: (AccountKind.LOAN, EntrySide.CREDIT),
    T.INVESTMENT_OPENING_BALANCE: (AccountKind.INVESTMENT, EntrySide.CREDIT),
    T.INVESTMENT_CONTRIBUTION: (AccountKind.INVESTMENT, EntrySide.CREDIT),
    T.INVESTMENT_LIQUIDATION: (AccountKind.INVESTMENT, EntrySide.DEBIT),
    # Credited to a savings account, or paid externally (no member account moves).
    T.DIVIDEND_PAYMENT: (None, EntrySide.CREDIT),
    T.ADJUSTMENT: (None, None),
    T.REVERSAL: (None, None),
}


def types_for(kind):
    return [t for t, (k, _) in TYPE_RULES.items() if k == kind]


SAVINGS_TYPES = types_for(AccountKind.SAVINGS)
LOAN_TYPES = types_for(AccountKind.LOAN)
INVESTMENT_TYPES = types_for(AccountKind.INVESTMENT)

# Defaults for CooperativeSettings.maker_checker_types: corrections, opening
# balances, and every entry that moves money out to the member.
DEFAULT_MAKER_CHECKER_TYPES = [
    T.ADJUSTMENT,
    T.REVERSAL,
    T.SAVINGS_OPENING_BALANCE,
    T.INVESTMENT_OPENING_BALANCE,
    T.SAVINGS_WITHDRAWAL,
    T.SAVINGS_CYCLE_PAYOUT,
    T.INVESTMENT_LIQUIDATION,
    T.LOAN_DISBURSEMENT,
    T.DIVIDEND_PAYMENT,
]


class BatchType(models.TextChoices):
    CONTRIBUTIONS = "CONTRIBUTIONS", "Savings contributions"
    LOAN_REPAYMENTS = "LOAN_REPAYMENTS", "Loan repayments"
    OPENING_BALANCES = "OPENING_BALANCES", "Savings opening balances"
    INVESTMENTS = "INVESTMENTS", "Investment contributions"
    INVESTMENT_OPENING_BALANCES = "INVESTMENT_OPENING_BALANCES", "Investment opening balances"
    DIVIDEND_PAYMENTS = "DIVIDEND_PAYMENTS", "Dividend payments"
    CYCLE_PAYOUTS = "CYCLE_PAYOUTS", "Savings cycle payouts"
    CLOSURE_SETTLEMENT = "CLOSURE_SETTLEMENT", "Account closure settlement"


class BatchStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    VALIDATED = "VALIDATED", "Validated"
    SUBMITTED = "SUBMITTED", "Submitted for approval"
    APPROVED = "APPROVED", "Approved"
    POSTED = "POSTED", "Posted"
    REJECTED = "REJECTED", "Rejected"
