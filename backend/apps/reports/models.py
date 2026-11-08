from django.db import models


class ReportAccess(models.Model):
    """
    Holds the reports permissions. Reports have no table of their own, so this
    model is unmanaged: Django creates its permissions but no database table.
    """

    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("view_reports", "View reports"),
            ("export_reports", "Export reports to Excel/PDF"),
        ]
