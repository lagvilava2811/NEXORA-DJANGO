from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from .services import merge_session_cart


@receiver(user_logged_in, dispatch_uid="store.merge_guest_cart_after_login")
def merge_guest_cart_after_login(sender, request, user, **kwargs):
    if request is not None:
        merge_session_cart(user, request.session)
