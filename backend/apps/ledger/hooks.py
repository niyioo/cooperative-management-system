"""
Posting hooks. Modules register functions to run when an entry of a given
type actually posts (at once, after second-officer approval, or with its
batch) or is rejected. Examples: a posted LOAN_DISBURSEMENT activates the
loan; a posted LOAN_REPAYMENT is allocated to instalments.

Hooks run inside the posting transaction, so a failing hook rolls the posting back.
"""
from collections import defaultdict

_posted = defaultdict(list)
_rejected = defaultdict(list)


def on_posted(txn_type):
    def decorator(func):
        _posted[txn_type].append(func)
        return func

    return decorator


def on_rejected(txn_type):
    def decorator(func):
        _rejected[txn_type].append(func)
        return func

    return decorator


def run_posted(entry):
    for func in _posted.get(entry.txn_type, ()):
        func(entry)


def run_rejected(entry):
    for func in _rejected.get(entry.txn_type, ()):
        func(entry)


_reversed = defaultdict(list)


def on_reversed(txn_type):
    """Run when a posted entry of `txn_type` is cancelled by a posted REVERSAL."""

    def decorator(func):
        _reversed[txn_type].append(func)
        return func

    return decorator


def run_reversed(original):
    for func in _reversed.get(original.txn_type, ()):
        func(original)
