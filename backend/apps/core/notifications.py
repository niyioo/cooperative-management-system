from .models import Notification


def notify(user, type, title, message):
    """Add an in-app notification for `user` (no-op without a user)."""
    if user is None:
        return None
    return Notification.objects.create(user=user, type=type, title=title, message=message)
