from django.db import models


class MoneyField(models.DecimalField):
    """Naira amount with kobo precision: numeric(15,2)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_digits", 15)
        kwargs.setdefault("decimal_places", 2)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if kwargs.get("max_digits") == 15:
            del kwargs["max_digits"]
        if kwargs.get("decimal_places") == 2:
            del kwargs["decimal_places"]
        return name, path, args, kwargs


class RateField(models.DecimalField):
    """Percentage rate, e.g. 12.5000 for 12.5%: numeric(7,4)."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_digits", 7)
        kwargs.setdefault("decimal_places", 4)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if kwargs.get("max_digits") == 7:
            del kwargs["max_digits"]
        if kwargs.get("decimal_places") == 4:
            del kwargs["decimal_places"]
        return name, path, args, kwargs
