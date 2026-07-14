from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import get_language

from .models import Review, UserAddress
from .security import normalize_email


FORM_TEXT = {
    "en": {
        "full_name": "Full name", "email": "Email", "phone": "Phone", "address": "Delivery address",
        "city": "City", "postal_code": "Postal code", "payment_method": "Payment method", "notes": "Order notes",
        "accept_terms": "I accept the terms and return policy", "cash_on_delivery": "Cash on delivery",
        "bank_transfer": "Bank transfer", "title": "Title", "address_title": "Address title", "review_title": "Review title", "address_line": "Street address",
        "is_default": "Use as default address", "coupon_code": "Promotional code", "rating": "Rating",
        "body": "Review", "username": "Username", "first_name": "First name", "last_name": "Last name",
        "password1": "Password", "password2": "Confirm password", "email_in_use": "An account already uses this email address.",
    },
    "ka": {
        "full_name": "სრული სახელი", "email": "ელფოსტა", "phone": "ტელეფონი", "address": "მიწოდების მისამართი",
        "city": "ქალაქი", "postal_code": "საფოსტო ინდექსი", "payment_method": "გადახდის მეთოდი", "notes": "შეკვეთის შენიშვნა",
        "accept_terms": "ვეთანხმები პირობებსა და დაბრუნების პოლიტიკას", "cash_on_delivery": "ნაღდი ანგარიშსწორება მიწოდებისას",
        "bank_transfer": "საბანკო გადარიცხვა", "title": "სათაური", "address_title": "მისამართის დასახელება", "review_title": "შეფასების სათაური", "address_line": "ქუჩისა და სახლის მისამართი",
        "is_default": "ნაგულისხმევ მისამართად გამოყენება", "coupon_code": "პრომო კოდი", "rating": "რეიტინგი",
        "body": "შეფასება", "username": "მომხმარებლის სახელი", "first_name": "სახელი", "last_name": "გვარი",
        "password1": "პაროლი", "password2": "გაიმეორე პაროლი", "email_in_use": "ამ ელფოსტით ანგარიში უკვე არსებობს.",
    },
    "ru": {
        "full_name": "Полное имя", "email": "Электронная почта", "phone": "Телефон", "address": "Адрес доставки",
        "city": "Город", "postal_code": "Почтовый индекс", "payment_method": "Способ оплаты", "notes": "Комментарий к заказу",
        "accept_terms": "Я принимаю условия и правила возврата", "cash_on_delivery": "Оплата при доставке",
        "bank_transfer": "Банковский перевод", "title": "Заголовок", "address_title": "Название адреса", "review_title": "Заголовок отзыва", "address_line": "Улица и дом",
        "is_default": "Использовать как основной адрес", "coupon_code": "Промокод", "rating": "Рейтинг",
        "body": "Отзыв", "username": "Имя пользователя", "first_name": "Имя", "last_name": "Фамилия",
        "password1": "Пароль", "password2": "Подтвердите пароль", "email_in_use": "Аккаунт с этим адресом электронной почты уже существует.",
    },
}


def form_text():
    language = (get_language() or "en").split("-")[0]
    return FORM_TEXT.get(language, FORM_TEXT["en"])


class AccessibleFormMixin:
    """Localize fields and attach stable accessible relationships."""

    autocomplete = {}

    def _apply_accessibility(self):
        labels = form_text()
        error_names = set(self.errors) if self.is_bound else set()
        for name, field in self.fields.items():
            if name in labels:
                field.label = labels[name]
            widget = field.widget
            widget.attrs.setdefault("id", f"id_{name}")
            described_by = []
            if field.help_text:
                described_by.append(f"help_{name}")
            if name in error_names:
                described_by.append(f"error_{name}")
                widget.attrs["aria-invalid"] = "true"
            if described_by:
                widget.attrs["aria-describedby"] = " ".join(described_by)
            else:
                widget.attrs.pop("aria-describedby", None)
            if field.required:
                widget.attrs.setdefault("aria-required", "true")
            widget.attrs.setdefault("autocomplete", self.autocomplete.get(name, "off"))


class CheckoutForm(AccessibleFormMixin, forms.Form):
    autocomplete = {
        "full_name": "name", "email": "email", "phone": "tel", "address": "street-address",
        "city": "address-level2", "postal_code": "postal-code",
    }

    full_name = forms.CharField(max_length=120)
    email = forms.EmailField(max_length=254)
    phone = forms.CharField(max_length=30)
    address = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows": 3}))
    city = forms.CharField(max_length=80, initial="Tbilisi")
    postal_code = forms.CharField(max_length=20, required=False)
    payment_method = forms.ChoiceField(choices=())
    notes = forms.CharField(max_length=1000, required=False, widget=forms.Textarea(attrs={"rows": 3}))
    accept_terms = forms.BooleanField(required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = form_text()
        self.fields["payment_method"].choices = (
            ("cash_on_delivery", labels["cash_on_delivery"]),
            ("bank_transfer", labels["bank_transfer"]),
        )
        self._apply_accessibility()


class AddressForm(AccessibleFormMixin, forms.ModelForm):
    autocomplete = {
        "full_name": "name", "phone": "tel", "city": "address-level2",
        "address_line": "street-address", "postal_code": "postal-code",
    }

    class Meta:
        model = UserAddress
        fields = ("title", "full_name", "phone", "city", "address_line", "postal_code", "is_default")
        widgets = {"address_line": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_accessibility()


class CouponForm(AccessibleFormMixin, forms.Form):
    autocomplete = {"coupon_code": "off"}
    coupon_code = forms.CharField(max_length=50)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_accessibility()


class ReviewForm(AccessibleFormMixin, forms.ModelForm):
    class Meta:
        model = Review
        fields = ("rating", "title", "body")
        widgets = {"body": forms.Textarea(attrs={"rows": 5, "maxlength": 3000})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["body"].required = True
        self._apply_accessibility()


class ProductRatingForm(AccessibleFormMixin, forms.Form):
    rating = forms.TypedChoiceField(
        choices=[(value, value) for value in range(1, 6)],
        coerce=int,
        widget=forms.RadioSelect,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_accessibility()


class SignupForm(AccessibleFormMixin, UserCreationForm):
    autocomplete = {
        "username": "username", "email": "email", "first_name": "given-name", "last_name": "family-name",
        "password1": "new-password", "password2": "new-password",
    }
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._apply_accessibility()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(form_text()["email_in_use"])
        return email


VERIFICATION_LABELS = {
    'en': ('Verification code', 'Enter the six-digit code.'),
    'ka': ('\u10d3\u10d0\u10d3\u10d0\u10e1\u10e2\u10e3\u10e0\u10d4\u10d1\u10d8\u10e1 \u10d9\u10dd\u10d3\u10d8', '\u10e8\u10d4\u10d8\u10d4\u10e7\u10d5\u10d0\u10dc\u10d4\u10d7 \u10d4\u10e5\u10d5\u10e1\u10dc\u10d8\u10e8\u10dc\u10d0 \u10d9\u10dd\u10d3\u10d8.'),
    'ru': ('\u041a\u043e\u0434 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0438\u044f', '\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u0448\u0435\u0441\u0442\u0438\u0437\u043d\u0430\u0447\u043d\u044b\u0439 \u043a\u043e\u0434.'),
}


class VerificationCodeForm(AccessibleFormMixin, forms.Form):
    code = forms.RegexField(
        regex=r'^\d{6}$',
        max_length=6,
        min_length=6,
        strip=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        language = (get_language() or 'en').split('-')[0]
        label, error = VERIFICATION_LABELS.get(language, VERIFICATION_LABELS['en'])
        self.fields['code'].label = label
        self.fields['code'].error_messages['invalid'] = error
        self.fields['code'].widget.attrs.update({
            'inputmode': 'numeric',
            'autocomplete': 'one-time-code',
            'maxlength': '6',
            'pattern': '[0-9]{6}',
        })
        self._apply_accessibility()


class VerificationRecoveryForm(AccessibleFormMixin, forms.Form):
    email = forms.EmailField(max_length=254)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].widget.attrs['autocomplete'] = 'email'
        self._apply_accessibility()

    def clean_email(self):
        return normalize_email(self.cleaned_data['email'])
