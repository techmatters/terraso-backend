from django.dispatch import receiver

from apps.auth.signals import user_signup_signal

from .models.memberships import Membership


@receiver(user_signup_signal)
def handle_pending_memberships(sender, **kwargs):
    user = kwargs["user"]
    pending_memberships = Membership.objects.filter(pending_email=user.email)
    for membership in pending_memberships:
        membership.pending_email = None
        membership.user = user
        membership.save()
