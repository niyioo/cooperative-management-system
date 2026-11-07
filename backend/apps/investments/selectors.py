from apps.ledger.selectors import ZERO, net_by

from .models import InvestmentAccount


def member_investment_position(member):
    principals = net_by("investment_account", member=member)
    accounts = InvestmentAccount.objects.filter(member=member).select_related("product")
    entries = [
        {
            "id": str(account.pk),
            "account_number": account.account_number,
            "product": account.product.name,
            "opened_on": account.opened_on,
            "status": account.status,
            "principal": principals.get(account.pk, ZERO),
        }
        for account in accounts
    ]
    return {"total_principal": sum((e["principal"] for e in entries), ZERO), "accounts": entries}
