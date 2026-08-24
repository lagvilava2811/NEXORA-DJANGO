import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from .models import PasswordResetCode


class PasswordResetDeliveryError(Exception):
    pass


class PasswordResetCooldownError(Exception):
    pass


class PasswordResetRateLimitError(Exception):
    pass


EMAIL_SUBJECT_EN = "Your NEXORA password reset code"
EMAIL_BODY_EN = "Your password reset code:\n\n{code}\n\nIt expires in {minutes} minutes."
EMAIL_SUBJECT_KA = "NEXORA - პაროლის აღდგენის კოდი"
EMAIL_BODY_KA = "თქვენი პაროლის აღდგენის კოდი:\n\n{code}\n\nკოდი მოქმედებს {minutes} წუთი."
EMAIL_SUBJECT_RU = "Код сброса пароля NEXORA"
EMAIL_BODY_RU = "Ваш код для сброса пароля:\n\n{code}\n\nКод действует {minutes} минут."

PAGE_TEXT = {
    "en": {
        "title": "Reset your password",
        "request_intro": "Enter your email and, if an account exists, we will send a six-digit reset code.",
        "done_title": "Enter your reset code",
        "done_intro": "Enter the six-digit code sent to your email address.",
        "submit_request": "Send reset code",
        "submit_code": "Verify code",
        "submit_password": "Save new password",
        "resend": "Send a new code",
        "resend_hint": "Didn't receive it?",
        "sent": "If an account exists for that email address, a fresh reset code has been sent.",
        "invalid": "The code is invalid.",
        "expired": "The code has expired. Request a new one.",
        "locked": "Too many attempts. Request a new code.",
        "wait": "Please wait before requesting another code.",
        "unavailable": "Password reset email is temporarily unavailable. Please try again.",
        "updated_title": "Password updated",
        "updated_body": "Your password has been changed successfully.",
    }
}
PAGE_TEXT["ka"] = PAGE_TEXT["en"].copy()
PAGE_TEXT["ka"].update(
    {
        "title": "პაროლის აღდგენა",
        "request_intro": "შეიყვანეთ ელფოსტა და თუ ანგარიში არსებობს, გამოგიგზავნით ექვსნიშნა აღდგენის კოდს.",
        "done_title": "შეიყვანეთ აღდგენის კოდი",
        "done_intro": "შეიყვანეთ ელფოსტაზე გამოგზავნილი ექვსნიშნა კოდი.",
        "submit_request": "კოდის გაგზავნა",
        "submit_code": "კოდის დადასტურება",
        "submit_password": "ახალი პაროლის შენახვა",
        "resend": "ახალი კოდის გაგზავნა",
        "resend_hint": "კოდი არ მიგიღიათ?",
        "sent": "თუ ეს ელფოსტა ანგარიშთანაა დაკავშირებული, ახალი აღდგენის კოდი გამოგზავნილია.",
        "invalid": "კოდი არასწორია.",
        "expired": "კოდის ვადა ამოიწურა. მოითხოვეთ ახალი.",
        "locked": "ცდების ლიმიტი ამოიწურა. მოითხოვეთ ახალი კოდი.",
        "wait": "ახალი კოდის მოთხოვნამდე ცოტა ხანს დაელოდეთ.",
        "unavailable": "პაროლის აღდგენის წერილი დროებით ვერ იგზავნება. სცადეთ ხელახლა.",
        "updated_title": "პაროლი განახლდა",
        "updated_body": "თქვენი პაროლი წარმატებით შეიცვალა.",
    }
)
PAGE_TEXT["ru"] = PAGE_TEXT["en"].copy()
PAGE_TEXT["ru"].update(
    {
        "title": "Сброс пароля",
        "request_intro": "Введите адрес электронной почты, и если аккаунт существует, мы отправим шестизначный код.",
        "done_title": "Введите код сброса",
        "done_intro": "Введите шестизначный код, отправленный на вашу почту.",
        "submit_request": "Отправить код",
        "submit_code": "Подтвердить код",
        "submit_password": "Сохранить новый пароль",
        "resend": "Отправить новый код",
        "resend_hint": "Не получили код?",
        "sent": "Если аккаунт для этого адреса существует, новый код сброса уже отправлен.",
        "invalid": "Неверный код.",
        "expired": "Срок действия кода истёк. Запросите новый.",
        "locked": "Слишком много попыток. Запросите новый код.",
        "wait": "Подождите перед повторным запросом кода.",
        "unavailable": "Письмо для сброса пароля временно недоступно. Повторите попытку.",
        "updated_title": "Пароль обновлён",
        "updated_body": "Ваш пароль успешно изменён.",
    }
)


def localized_password_reset_text(language):
    language = (language or "en").split("-")[0]
    return PAGE_TEXT.get(language, PAGE_TEXT["en"])


def localized_email(language):
    language = (language or "en").split("-")[0]
    if language == "ka":
        return EMAIL_SUBJECT_KA, EMAIL_BODY_KA
    if language == "ru":
        return EMAIL_SUBJECT_RU, EMAIL_BODY_RU
    return EMAIL_SUBJECT_EN, EMAIL_BODY_EN


def issue_password_reset_code(user, language="en", enforce_cooldown=False):
    now = timezone.now()
    expiry_seconds = max(60, int(getattr(settings, "PASSWORD_RESET_CODE_EXPIRY_SECONDS", 600)))
    cooldown_seconds = max(1, int(getattr(settings, "PASSWORD_RESET_CODE_RESEND_COOLDOWN", 60)))
    max_sends = max(1, int(getattr(settings, "PASSWORD_RESET_CODE_MAX_SENDS_PER_HOUR", 5)))

    if not user.is_active or not user.has_usable_password():
        return None

    with transaction.atomic():
        record, created = PasswordResetCode.objects.select_for_update().get_or_create(
            user=user,
            defaults={
                "code_digest": make_password("unissued"),
                "expires_at": now,
                "resend_available_at": now,
                "send_window_started_at": now,
                "pending_reset_at": now,
            },
        )
        if enforce_cooldown and not created and now < record.resend_available_at:
            raise PasswordResetCooldownError

        window_expired = now >= record.send_window_started_at + timedelta(hours=1)
        send_count = 0 if window_expired else record.send_count
        window_started = now if window_expired else record.send_window_started_at
        if send_count >= max_sends:
            raise PasswordResetRateLimitError

        code = f"{secrets.randbelow(1_000_000):06d}"
        minutes = max(1, expiry_seconds // 60)
        subject, body_template = localized_email(language)
        message = body_template.format(code=code, minutes=minutes)
        body = render_to_string("email/password_reset_code.txt", {"message": message})
        html_body = render_to_string(
            "email/password_reset_code.html",
            {"message": message, "language": language},
        )
        try:
            sent = send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
                html_message=html_body,
            )
        except Exception as exc:
            raise PasswordResetDeliveryError from exc
        if sent != 1:
            raise PasswordResetDeliveryError

        record.code_digest = make_password(code)
        record.expires_at = now + timedelta(seconds=expiry_seconds)
        record.resend_available_at = now + timedelta(seconds=cooldown_seconds)
        record.failed_attempts = 0
        record.send_count = send_count + 1
        record.send_window_started_at = window_started
        record.verified_at = None
        record.pending_reset_at = now
        record.used_at = None
        record.save()
        return record
