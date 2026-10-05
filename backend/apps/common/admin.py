from django.contrib import admin
from django.core.cache import cache
from django.http import HttpResponse

from apps.audit.services import record

from .middleware import client_ip
from .models import NumberSequence

# The Django admin is a Super Administrator support console only; officers work
# in the React portal. Restrict the whole site to active superusers.
admin.site.has_permission = lambda request: bool(
    request.user.is_active and request.user.is_superuser
)
admin.site.site_header = "EMDI Cooperative — Support Console"
admin.site.site_title = "EMDI Cooperative"

# The console has its own sign-in page, outside the API's login throttle, so it
# gets the same protection: failed attempts are audited, and an address that
# keeps failing is locked out for a while.
ADMIN_LOGIN_ATTEMPTS = 5
ADMIN_LOGIN_LOCKOUT_SECONDS = 15 * 60
_admin_login = admin.site.login


def _throttled_admin_login(request, extra_context=None):
    if request.method != "POST":
        return _admin_login(request, extra_context)
    key = f"admin-login-failures:{client_ip(request)}"
    failures = cache.get(key, 0)
    if failures >= ADMIN_LOGIN_ATTEMPTS:
        return HttpResponse("Too many failed sign-in attempts. Try again later.", status=429, content_type="text/plain")
    response = _admin_login(request, extra_context)
    if request.user.is_authenticated and admin.site.has_permission(request):
        cache.delete(key)
    else:
        cache.set(key, failures + 1, ADMIN_LOGIN_LOCKOUT_SECONDS)
        record("auth.admin_login_failed", metadata={"username": request.POST.get("username", "")[:254]})
    return response


admin.site.login = _throttled_admin_login


SENSITIVE_FIELDS = {"password"}


def _display(value):
    if value is None:
        return None
    if hasattr(value, "_meta"):  # model instance
        return str(value)
    if hasattr(value, "name") and hasattr(value, "storage"):  # file
        return value.name or None
    if isinstance(value, (list, tuple, set)):
        return [_display(v) for v in value]
    return value


class AuditedAdminMixin:
    """
    The support console bypasses the API services, so record every change made
    through it in the audit log, with before/after values (ARCHITECTURE.md D11).
    """

    def _action(self, obj, verb):
        return f"admin.{obj._meta.label_lower}.{verb}"

    def _m2m_names(self, obj):
        return {f.name for f in obj._meta.many_to_many}

    def save_model(self, request, obj, form, change):
        m2m = self._m2m_names(obj)
        fields = [f for f in form.changed_data if f not in m2m]
        before = {}
        if change:
            old = type(obj)._default_manager.filter(pk=obj.pk).first()
            before = {f: getattr(old, f, None) for f in fields} if old else {}
        super().save_model(request, obj, form, change)
        changes = {
            f: ["(hidden)", "(changed)"] if f in SENSITIVE_FIELDS else [_display(before.get(f)), _display(getattr(obj, f, None))]
            for f in fields
        }
        record(self._action(obj, "updated" if change else "created"), actor=request.user, obj=obj,
               changes=changes, metadata={"via": "support_console"})

    def save_related(self, request, form, formsets, change):
        obj = form.instance
        m2m_changed = [f for f in form.changed_data if f in self._m2m_names(obj)]
        before = {f: sorted(str(x) for x in getattr(obj, f).all()) for f in m2m_changed} if change else {}
        super().save_related(request, form, formsets, change)
        changes = {f: [before.get(f, []), sorted(str(x) for x in getattr(obj, f).all())] for f in m2m_changed}
        inlines = []
        for formset in formsets:
            created = getattr(formset, "new_objects", [])
            changed = getattr(formset, "changed_objects", [])
            deleted = getattr(formset, "deleted_objects", [])
            if created or changed or deleted:
                inlines.append({
                    "model": formset.model._meta.label_lower,
                    "created": [str(o) for o in created],
                    "changed": [{"object": str(o), "fields": fields} for o, fields in changed],
                    "deleted": [str(o) for o in deleted],
                })
        if changes or inlines:
            record(self._action(obj, "relations_changed"), actor=request.user, obj=obj,
                   changes=changes, metadata={"via": "support_console", "inlines": inlines})

    def delete_model(self, request, obj):
        record(self._action(obj, "deleted"), actor=request.user, obj=obj, metadata={"via": "support_console"})
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for obj in queryset:
            record(self._action(obj, "deleted"), actor=request.user, obj=obj, metadata={"via": "support_console", "bulk": True})
        super().delete_queryset(request, queryset)


class ReadOnlyAdminMixin:
    """For append-only records (ledger, audit log): viewable, never editable here."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class NoDeleteAdminMixin:
    """Financial and membership records are deactivated, never deleted."""

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


@admin.register(NumberSequence)
class NumberSequenceAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("key", "last_value", "updated_at")
    search_fields = ("key",)
