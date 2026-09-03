from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db import models
from django.utils import timezone


class EmailVerification(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='email_verification')
    code_digest = models.CharField(max_length=128)
    link_token_digest = models.CharField(max_length=128, blank=True, default='')
    expires_at = models.DateTimeField()
    resend_available_at = models.DateTimeField()
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    send_count = models.PositiveSmallIntegerField(default=0)
    send_window_started_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)
    pending_verification_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def check_code(self, candidate):
        return bool(self.code_digest) and check_password(str(candidate), self.code_digest)

    def check_link_token(self, candidate):
        return bool(self.link_token_digest) and check_password(str(candidate), self.link_token_digest)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_locked(self):
        return self.failed_attempts >= getattr(settings, 'EMAIL_VERIFICATION_MAX_ATTEMPTS', 5)


class PasswordResetCode(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='password_reset_code')
    code_digest = models.CharField(max_length=128)
    expires_at = models.DateTimeField()
    resend_available_at = models.DateTimeField()
    failed_attempts = models.PositiveSmallIntegerField(default=0)
    send_count = models.PositiveSmallIntegerField(default=0)
    send_window_started_at = models.DateTimeField(default=timezone.now)
    verified_at = models.DateTimeField(null=True, blank=True)
    pending_reset_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def check_code(self, candidate):
        return bool(self.code_digest) and check_password(str(candidate), self.code_digest)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_locked(self):
        return self.failed_attempts >= getattr(settings, 'PASSWORD_RESET_CODE_MAX_ATTEMPTS', 5)


class AccountDeletionRequest(models.Model):
    """Auditable request; fulfillment remains an operator action."""

    STATUS_CHOICES = (("pending", "Pending"), ("cancelled", "Cancelled"), ("completed", "Completed"))
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="deletion_request")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    requested_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(blank=True)

    class Meta:
        ordering = ("-requested_at",)

    def __str__(self):
        return f"Account deletion request for {self.user_id} ({self.status})"

