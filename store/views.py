import json
import re
from urllib.parse import urlencode
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordResetForm
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, F, Max, Min, Q
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import get_language
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .context_processors import COPIES
from .gemini import gemini_guide_reply
from .forms import AddressForm, CheckoutForm, CouponForm, ProductRatingForm, ReviewForm, SignupForm, VerificationCodeForm, VerificationRecoveryForm, form_text
from .models import (
    Brand,
    Category,
    Coupon,
    EmailVerification,
    Order,
    OrderItem,
    Product,
    ProductVariant,
    ProductRating,
    ReturnRequest,
    Review,
    UserAddress,
    WarrantyClaim,
    Wishlist,
)
from .verification import (
    VerificationCooldownError,
    VerificationDeliveryError,
    VerificationRateLimitError,
    VerificationStateError,
    issue_verification,
    localized_page_text,
    mask_email,
)
from .security import cache_rate_limited, login_rate_limited, normalize_email, request_ip
from .services import (
    CheckoutError,
    MAX_CART_QUANTITY,
    cart_rows,
    cart_totals,
    create_order_from_session,
    safe_quantity,
    valid_coupon,
)


def rows(request):
    lines, total = cart_rows(request.session)
    return [(line.product, line.quantity, line.line_total) for line in lines], total


def _safe_next(request, fallback):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return reverse(fallback)


def _decimal_param(value):
    if not value:
        return None
    try:
        parsed = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if parsed < 0 or parsed > Decimal("1000000"):
        return None
    return parsed


@require_GET
def home(request):
    products = Product.objects.storefront().order_by("-is_featured", "-rating", "name")[:12]
    hero_product = (
        Product.objects.storefront()
        .filter(slug="asus-rog-zephyrus-g14")
        .first()
        or Product.objects.storefront().filter(category__slug="laptops").order_by("-is_featured", "-rating", "name").first()
    )
    categories = Category.objects.filter(is_active=True).order_by("display_order", "name")
    featured_brands = Brand.objects.filter(is_featured=True, products_link__is_published=True).distinct().order_by("display_order", "name")[:8]
    return render(
        request,
        "home.html",
        {
            "products": products,
            "hero_product": hero_product,
            "categories": categories,
            "featured_brands": featured_brands,
        },
    )


@require_GET
def shop(request):
    products = Product.objects.storefront()
    query = request.GET.get("q", "").strip()[:120]
    if query:
        products = products.filter(
            Q(name__icontains=query)
            | Q(name_ka__icontains=query)
            | Q(name_en__icontains=query)
            | Q(name_ru__icontains=query)
            | Q(description__icontains=query)
            | Q(short_description__icontains=query)
            | Q(full_description__icontains=query)
            | Q(brand__icontains=query)
            | Q(sku__icontains=query)
        )

    category = request.GET.get("category", "")[:100]
    if category:
        products = products.filter(category__slug=category)
    brand = request.GET.get("brand", "").strip()[:100]
    if brand:
        products = products.filter(
            Q(brand__iexact=brand) | Q(brand_obj__slug=brand) | Q(brand_obj__name__iexact=brand)
        )

    min_price = _decimal_param(request.GET.get("min_price"))
    max_price = _decimal_param(request.GET.get("max_price"))
    if min_price is not None:
        products = products.filter(price__gte=min_price)
    if max_price is not None:
        products = products.filter(price__lte=max_price)
    if request.GET.get("in_stock") == "1":
        products = products.filter(stock__gt=0)

    min_rating = _decimal_param(request.GET.get("min_rating"))
    if min_rating is not None and min_rating <= 5:
        products = products.filter(rating__gte=min_rating)
    if request.GET.get("discount") == "1":
        products = products.filter(compare_at_price__isnull=False, compare_at_price__gt=F("price"))

    sort = request.GET.get("sort", "featured")
    ordering = {
        "price-asc": "price",
        "price-desc": "-price",
        "rating": "-rating",
        "new": "-created_at",
        "name": "name",
    }.get(sort, "-is_featured")
    products = products.order_by(ordering, "name", "pk")

    published = Product.objects.published()
    available_brands = Brand.objects.filter(
        products_link__in=published,
    ).distinct().order_by("name")
    price_range = published.aggregate(min_price=Min("price"), max_price=Max("price"))
    page = Paginator(products, 24, orphans=3).get_page(request.GET.get("page"))
    return render(
        request,
        "shop.html",
        {
            "products": page,
            "page": page,
            "query": query,
            "categories": Category.objects.filter(is_active=True).order_by("display_order", "name"),
            "category": category,
            "current_brand": brand,
            "available_brands": available_brands,
            "price_range": price_range,
            "current_sort": sort,
            "current_min_price": request.GET.get("min_price", ""),
            "current_max_price": request.GET.get("max_price", ""),
            "current_min_rating": request.GET.get("min_rating", ""),
            "current_stock_filter": request.GET.get("in_stock", ""),
            "current_discount": request.GET.get("discount", ""),
        },
    )


def _product_context(request, product_item, review_form=None):
    summary = product_item.ratings.aggregate(average=Avg('rating'), count=Count('id'))
    rating_count = summary['count'] or 0
    rating_average = round(float(summary['average']), 1) if rating_count else None
    product_item.rating = rating_average if rating_count else '—'
    product_item.rating_average = rating_average or 0
    product_item.rating_count = rating_count
    user_rating = None
    if request.user.is_authenticated:
        user_rating = product_item.ratings.filter(user=request.user).values_list('rating', flat=True).first()
    return {
        'rating_average': rating_average,
        'rating_count': rating_count,
        'rating_choices': range(1, 6),
        'user_rating': user_rating,
        "product": product_item,
        "related": Product.objects.storefront().filter(category=product_item.category).exclude(pk=product_item.pk).order_by("-rating")[:4],
        "gallery": product_item.gallery_images,
        "reviews": product_item.reviews.filter(is_approved=True).select_related("user").order_by("-created_at")[:10],
        "review_form": review_form or ReviewForm(),
        "is_wishlisted": request.user.is_authenticated and Wishlist.objects.filter(user=request.user, product=product_item).exists(),
    }


@require_GET
def product(request, slug):
    product_item = get_object_or_404(Product.objects.storefront(), slug=slug)
    return render(request, "product.html", _product_context(request, product_item))


def _bag_key(product_id, variant_id=None):
    """Keep product-only entries backwards compatible and variants distinct."""
    return f"{product_id}:{variant_id}" if variant_id else str(product_id)


def _requested_variant(product_item, value):
    if not value:
        return None
    return get_object_or_404(
        ProductVariant.objects.select_related("product"),
        pk=value,
        product=product_item,
        is_active=True,
    )


def _available_stock(product_item, variant=None):
    return min(product_item.stock, variant.stock_quantity) if variant else product_item.stock


@require_GET
def bag(request):
    totals = cart_totals(request.session, request.user)
    return render(
        request,
        "bag.html",
        {
            "items": totals["lines"],
            "total": totals["subtotal"],
            "shipping": totals["shipping"],
            "discount": totals["discount"],
            "grand_total": totals["total"],
            "coupon": totals["coupon"],
            "coupon_form": CouponForm(),
        },
    )


@require_POST
def add(request, id):
    product_item = get_object_or_404(Product.objects.published(), pk=id)
    variant = _requested_variant(product_item, request.POST.get("variant"))
    quantity = safe_quantity(request.POST.get("quantity"), default=1)
    bag_data = request.session.get("bag", {}) if isinstance(request.session.get("bag", {}), dict) else {}
    key = _bag_key(product_item.pk, variant.pk if variant else None)
    current = safe_quantity(bag_data.get(key), default=0)
    bag_data[key] = min(_available_stock(product_item, variant), current + max(1, quantity), MAX_CART_QUANTITY)
    request.session["bag"] = bag_data
    request.session.modified = True
    return redirect(_safe_next(request, "bag"))


@require_POST
def update(request, id):
    product_item = get_object_or_404(Product.objects.published(), pk=id)
    variant = _requested_variant(product_item, request.POST.get("variant"))
    bag_data = request.session.get("bag", {}) if isinstance(request.session.get("bag", {}), dict) else {}
    key = _bag_key(product_item.pk, variant.pk if variant else None)
    quantity = safe_quantity(request.POST.get("quantity"), default=0)
    if quantity:
        bag_data[key] = min(quantity, _available_stock(product_item, variant), MAX_CART_QUANTITY)
    else:
        bag_data.pop(key, None)
    request.session["bag"] = bag_data
    request.session.modified = True
    return redirect("bag")


def checkout(request):
    totals = cart_totals(request.session, request.user)
    if not totals["lines"]:
        messages.info(request, "Your bag is empty.")
        return redirect("shop")

    initial = {}
    if request.user.is_authenticated:
        default_address = request.user.addresses.filter(is_default=True).first()
        initial.update({"email": request.user.email, "full_name": request.user.get_full_name()})
        if default_address:
            initial.update(
                {
                    "full_name": default_address.full_name,
                    "phone": default_address.phone,
                    "city": default_address.city,
                    "address": default_address.address_line,
                    "postal_code": default_address.postal_code,
                }
            )
    form = CheckoutForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            order = create_order_from_session(request.session, form.cleaned_data, request.user)
        except CheckoutError as exc:
            form.add_error(None, str(exc))
        else:
            request.session["bag"] = {}
            request.session.pop("coupon_id", None)
            allowed = request.session.get("order_refs", [])
            request.session["order_refs"] = (allowed + [order.reference])[-10:]
            request.session.modified = True
            return redirect("order_success", reference=order.reference)

    addresses = request.user.addresses.all() if request.user.is_authenticated else []
    return render(
        request,
        "checkout.html",
        {
            "form": form,
            "items": totals["lines"],
            "total": totals["subtotal"],
            "shipping": totals["shipping"],
            "discount": totals["discount"],
            "coupon": totals["coupon"],
            "grand_total": totals["total"],
            "addresses": addresses,
        },
    )


@require_GET
def order_success(request, reference):
    order = get_object_or_404(Order.objects.select_related("user").prefetch_related("items__product"), reference=reference)
    if order.user_id:
        if not request.user.is_authenticated or order.user_id != request.user.id:
            raise Http404
    elif reference not in request.session.get("order_refs", []):
        raise Http404
    return render(request, "success.html", {"order": order})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("cabinet")
    form = AuthenticationForm(request, data=request.POST or None)
    for name, field in form.fields.items():
        field.widget.attrs.update(
            {
                "id": f"id_{name}",
                "aria-describedby": f"error_{name}",
                "autocomplete": "current-password" if "password" in name else "username",
            }
        )
    if request.method == "POST":
        if login_rate_limited(
            request,
            "login",
            request.POST.get("username", ""),
            ip_limit=getattr(settings, "LOGIN_RATE_LIMIT_PER_IP", 10),
            account_limit=getattr(settings, "LOGIN_RATE_LIMIT_PER_ACCOUNT", 5),
            window_seconds=getattr(settings, "LOGIN_RATE_LIMIT_WINDOW", 900),
        ):
            form.add_error(None, "Too many sign-in attempts. Please wait and try again.")
        elif form.is_valid():
            login(request, form.get_user())
            return redirect(_safe_next(request, "cabinet"))
    return render(request, "login.html", {"form": form})


@require_http_methods(["GET", "POST"])
def password_reset_request(request):
    """Issue Django's signed, expiring password-reset link without enumeration."""
    form = PasswordResetForm(request.POST or None)
    if request.method == "POST":
        email = normalize_email(request.POST.get("email", ""))
        limited = login_rate_limited(
            request,
            "password-reset",
            email,
            ip_limit=getattr(settings, "PASSWORD_RESET_RATE_LIMIT_PER_IP", 5),
            account_limit=getattr(settings, "PASSWORD_RESET_RATE_LIMIT_PER_ACCOUNT", 3),
            window_seconds=getattr(settings, "PASSWORD_RESET_RATE_LIMIT_WINDOW", 3600),
        )
        if limited:
            form.add_error(None, "Too many reset requests. Please wait and try again.")
        elif form.is_valid():
            form.save(
                request=request,
                use_https=request.is_secure(),
                from_email=settings.DEFAULT_FROM_EMAIL,
                email_template_name="registration/password_reset_email.txt",
                html_email_template_name="registration/password_reset_email.html",
                subject_template_name="registration/password_reset_subject.txt",
            )
            return redirect("password_reset_done")
    return render(request, "registration/password_reset_form.html", {"form": form})


def _legacy_signup_view(request):
    if request.user.is_authenticated:
        return redirect("cabinet")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("cabinet")
    return render(request, "signup.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('cabinet')
    form = SignupForm(request.POST or None)
    text = localized_page_text(get_language())
    if request.method == 'POST' and form.is_valid():
        email = normalize_email(form.cleaned_data['email'])
        window = getattr(settings, 'SIGNUP_RATE_LIMIT_WINDOW', 3600)
        limited_ip = cache_rate_limited(
            'signup-ip', request_ip(request), getattr(settings, 'SIGNUP_RATE_LIMIT_PER_IP', 10), window,
        )
        limited_email = cache_rate_limited(
            'signup-email', email, getattr(settings, 'SIGNUP_RATE_LIMIT_PER_EMAIL', 3), window,
        )
        if limited_ip or limited_email:
            form.add_error(None, text['unavailable'])
        else:
            try:
                with transaction.atomic():
                    user = form.save(commit=False)
                    user.email = email
                    user.is_active = False
                    user.save()
                    issue_verification(user, get_language())
            except IntegrityError:
                form.add_error('email', form_text()['email_in_use'])
            except (VerificationDeliveryError, VerificationStateError):
                form.add_error(None, text['unavailable'])
            else:
                request.session['pending_verification_user_id'] = user.pk
                request.session['post_verify_next'] = _safe_next(request, 'cabinet')
                return redirect('verify_email')
    return render(request, 'signup.html', {'form': form})


def _verification_record(request):
    user_id = request.session.get('pending_verification_user_id')
    if not user_id:
        return None
    return EmailVerification.objects.select_related('user').filter(
        user_id=user_id,
        verified_at__isnull=True,
        pending_verification_at__isnull=False,
        user__is_active=False,
    ).first()


def verify_email_view(request):
    if request.user.is_authenticated:
        return redirect('cabinet')
    record = _verification_record(request)
    text = localized_page_text(get_language())
    form = VerificationCodeForm(request.POST or None)
    recovery_form = VerificationRecoveryForm()
    verified_user = None

    if record is None:
        context = {
            'form': form,
            'recovery_form': recovery_form,
            'text': text,
            'masked_email': '***',
            'can_verify': False,
        }
        return render(request, 'verify_email.html', context)

    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            record = EmailVerification.objects.select_for_update().select_related('user').get(pk=record.pk)
            if record.verified_at is not None or record.pending_verification_at is None or record.user.is_active:
                form.add_error('code', text['invalid'])
            elif record.is_expired:
                form.add_error('code', text['expired'])
            elif record.is_locked:
                form.add_error('code', text['locked'])
            elif record.check_code(form.cleaned_data['code']):
                record.user.is_active = True
                record.user.save(update_fields=['is_active'])
                record.verified_at = timezone.now()
                record.pending_verification_at = None
                record.code_digest = ''
                record.save(update_fields=['verified_at', 'pending_verification_at', 'code_digest', 'updated_at'])
                verified_user = record.user
            else:
                record.failed_attempts += 1
                record.save(update_fields=['failed_attempts', 'updated_at'])
                message = text['locked'] if record.is_locked else text['invalid']
                form.add_error('code', message)

    if verified_user is not None:
        login(request, verified_user, backend='django.contrib.auth.backends.ModelBackend')
        request.session.pop('pending_verification_user_id', None)
        target = request.session.pop('post_verify_next', reverse('cabinet'))
        if not url_has_allowed_host_and_scheme(target, {request.get_host()}, request.is_secure()):
            target = reverse('cabinet')
        return redirect(target)

    context = {
        'form': form,
        'recovery_form': recovery_form,
        'text': text,
        'masked_email': mask_email(record.user.email),
        'can_verify': True,
    }
    return render(request, 'verify_email.html', context)


@require_POST
def resend_verification_view(request):
    text = localized_page_text(get_language())
    record = _verification_record(request)
    recovery_form = VerificationRecoveryForm(request.POST)
    can_verify = bool(request.session.get('pending_verification_user_id')) or recovery_form.is_valid()
    email = record.user.email if record else ''
    if recovery_form.is_valid():
        email = recovery_form.cleaned_data['email']
    notice = text['sent']

    window = getattr(settings, 'VERIFICATION_RECOVERY_RATE_LIMIT_WINDOW', 3600)
    limited_ip = cache_rate_limited(
        'recovery-ip', request_ip(request), getattr(settings, 'VERIFICATION_RECOVERY_RATE_LIMIT_PER_IP', 10), window,
    )
    limited_email = cache_rate_limited(
        'recovery-email', email or 'anonymous',
        getattr(settings, 'VERIFICATION_RECOVERY_RATE_LIMIT_PER_EMAIL', 5), window,
    )
    if not limited_ip and not limited_email and email:
        record = EmailVerification.objects.select_related('user').filter(
            user__email__iexact=email,
            user__is_active=False,
            verified_at__isnull=True,
            pending_verification_at__isnull=False,
        ).first()
        if record is not None:
            try:
                issue_verification(record.user, get_language(), enforce_cooldown=True)
            except (
                VerificationCooldownError,
                VerificationDeliveryError,
                VerificationRateLimitError,
                VerificationStateError,
            ):
                pass
            else:
                request.session['pending_verification_user_id'] = record.user_id

    context = {
        'form': VerificationCodeForm(),
        'recovery_form': recovery_form,
        'text': text,
        'notice': notice,
        'masked_email': mask_email(email),
        'can_verify': can_verify,
    }
    return render(request, 'verify_email.html', context)


def _cabinet_context(request, address_form=None):
    return {
        "orders": request.user.orders.prefetch_related("items__product").order_by("-created_at"),
        "addresses": request.user.addresses.all(),
        "address_form": address_form or AddressForm(),
        "wishlist": request.user.wishlists.select_related("product").filter(product__is_published=True),
        "returns": ReturnRequest.objects.filter(user=request.user).order_by("-created_at"),
        "warranty_claims": WarrantyClaim.objects.filter(user=request.user).order_by("-created_at"),
    }


def _localized_copy(key):
    language = (get_language() or "en").split("-")[0]
    return COPIES.get(language, COPIES["en"]).get(key, COPIES["en"].get(key, key))


@login_required(login_url="login")
@require_GET
def cabinet_view(request):
    return render(request, "cabinet.html", _cabinet_context(request))


@login_required(login_url="login")
@require_POST
def add_address_view(request):
    form = AddressForm(request.POST)
    if form.is_valid():
        address = form.save(commit=False)
        address.user = request.user
        if address.is_default:
            request.user.addresses.update(is_default=False)
        address.save()
        messages.success(request, _localized_copy("address_saved"))
        return redirect("cabinet")
    messages.error(request, _localized_copy("address_error"))
    return render(request, "cabinet.html", _cabinet_context(request, form), status=400)

@login_required(login_url="login")
@require_POST
def delete_address_view(request, id):
    get_object_or_404(UserAddress, pk=id, user=request.user).delete()
    messages.success(request, _localized_copy("address_removed"))
    return redirect("cabinet")


@require_POST
def apply_coupon_view(request):
    form = CouponForm(request.POST)
    totals = cart_totals(request.session, request.user)
    coupon = None
    if form.is_valid():
        candidate = Coupon.objects.filter(code__iexact=form.cleaned_data["coupon_code"]).first()
        coupon = valid_coupon(candidate.pk if candidate else None, totals["subtotal"], user=request.user)
    if coupon:
        request.session["coupon_id"] = coupon.pk
        messages.success(request, _localized_copy("coupon_applied"))
    else:
        request.session.pop("coupon_id", None)
        messages.error(request, _localized_copy("coupon_invalid"))
    request.session.modified = True
    return redirect("checkout")


def _cart_drawer_response(request):
    lines, total = cart_rows(request.session)
    currency = COPIES.get(get_language(), COPIES["en"]).get("currency_symbol", "₾")
    return JsonResponse(
        {
            "items": [
                {
                    "id": line.product.id,
                    "variant_id": line.variant.id if line.variant else None,
                    "name": f"{line.product.localized_name} — {line.variant.name}" if line.variant else line.product.localized_name,
                    "image": line.product.display_image,
                    "qty": line.quantity,
                    "price": str(line.unit_price),
                    "line_total": str(line.line_total),
                    "url": line.product.get_absolute_url(),
                }
                for line in lines
            ],
            "total": f"{total} {currency}",
        }
    )


@require_GET
def cart_drawer_ajax(request):
    return _cart_drawer_response(request)


@require_POST
def cart_add_ajax(request, id):
    product_item = get_object_or_404(Product.objects.published(), pk=id)
    variant = _requested_variant(product_item, request.POST.get("variant"))
    bag_data = request.session.get("bag", {}) if isinstance(request.session.get("bag", {}), dict) else {}
    key = _bag_key(product_item.pk, variant.pk if variant else None)
    current = safe_quantity(bag_data.get(key), default=0)
    requested = safe_quantity(request.POST.get("quantity"), default=1)
    bag_data[key] = min(_available_stock(product_item, variant), current + max(1, requested), MAX_CART_QUANTITY)
    request.session["bag"] = bag_data
    request.session.modified = True
    return _cart_drawer_response(request)


@require_POST
def cart_update_ajax(request, id):
    product_item = get_object_or_404(Product.objects.published(), pk=id)
    variant = _requested_variant(product_item, request.POST.get("variant"))
    bag_data = request.session.get("bag", {}) if isinstance(request.session.get("bag", {}), dict) else {}
    key = _bag_key(product_item.pk, variant.pk if variant else None)
    quantity = safe_quantity(request.POST.get("quantity"), default=0)
    if quantity:
        bag_data[key] = min(quantity, _available_stock(product_item, variant), MAX_CART_QUANTITY)
    else:
        bag_data.pop(key, None)
    request.session["bag"] = bag_data
    request.session.modified = True
    return _cart_drawer_response(request)


@login_required(login_url="login")
@require_POST
def toggle_wishlist(request, id):
    product_item = get_object_or_404(Product.objects.published(), pk=id)
    wish, created = Wishlist.objects.get_or_create(user=request.user, product=product_item)
    if not created:
        wish.delete()
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"added": created})
    return redirect(_safe_next(request, "shop"))


@login_required(login_url="login")
@require_GET
def compare_view(request):
    ids = request.session.get("compare", [])
    products = Product.objects.storefront().filter(pk__in=ids)
    return render(request, "compare.html", {"products": products})


@require_POST
def toggle_compare(request, id):
    get_object_or_404(Product.objects.published(), pk=id)
    ids = [value for value in request.session.get("compare", []) if isinstance(value, int)]
    if id in ids:
        ids.remove(id)
    elif len(ids) < 4:
        ids.append(id)
    request.session["compare"] = ids
    request.session.modified = True
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"compare": ids})
    return redirect(_safe_next(request, "shop"))


@login_required(login_url="login")
@require_POST
def add_review(request, slug):
    product_item = get_object_or_404(Product.objects.published(), slug=slug)
    form = ReviewForm(request.POST)
    if form.is_valid():
        verified = OrderItem.objects.filter(
            order__user=request.user,
            order__status__in=("confirmed", "processing", "shipped", "delivered"),
            product=product_item,
        ).exists()
        Review.objects.update_or_create(
            user=request.user,
            product=product_item,
            defaults={**form.cleaned_data, "is_verified_purchase": verified, "is_approved": False},
        )
        messages.success(request, _localized_copy("review_submitted"))
        return redirect("product", slug=slug)
    messages.error(request, _localized_copy("review_error"))
    return render(request, "product.html", _product_context(request, product_item, form), status=400)


def _rating_wants_json(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '')


@require_POST
def rate_product(request, slug):
    product_url = reverse('product', kwargs={'slug': slug})
    login_url = reverse('login') + '?' + urlencode({'next': product_url})
    if not request.user.is_authenticated:
        if _rating_wants_json(request):
            return JsonResponse({'ok': False, 'error': _localized_copy('rating_login_required'), 'login_url': login_url}, status=401)
        return redirect(login_url)
    product_item = get_object_or_404(Product.objects.published(), slug=slug)
    content_type = request.content_type or ''
    if int(request.META.get('CONTENT_LENGTH') or 0) > 2048:
        return JsonResponse({'ok': False, 'error': _localized_copy('rating_invalid')}, status=413)
    if content_type == 'application/json':
        try:
            payload = json.loads(request.body or b'{}')
        except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        if not isinstance(payload, dict):
            return JsonResponse({'ok': False, 'error': _localized_copy('rating_invalid')}, status=400)
    elif content_type in {'application/x-www-form-urlencoded', 'multipart/form-data'}:
        payload = request.POST
    else:
        return JsonResponse({'ok': False, 'error': _localized_copy('rating_invalid')}, status=415)
    form = ProductRatingForm(payload)
    if not form.is_valid():
        message = _localized_copy('rating_invalid')
        if _rating_wants_json(request):
            return JsonResponse({'ok': False, 'error': message}, status=400)
        messages.error(request, message)
        return redirect('product', slug=slug)
    with transaction.atomic():
        locked = Product.objects.select_for_update().get(pk=product_item.pk)
        rating, _ = ProductRating.objects.update_or_create(
            product=locked, user=request.user,
            defaults={'rating': form.cleaned_data['rating']},
        )
        locked.refresh_from_db(fields=['rating', 'rating_count'])
        average = locked.rating
        rating_count = locked.rating_count
    message = _localized_copy('rating_saved')
    if _rating_wants_json(request):
        return JsonResponse({'ok': True, 'user_rating': rating.rating, 'average': float(average), 'count': rating_count, 'message': message})
    messages.success(request, message)
    return redirect('product', slug=slug)


GUIDE_TEXT = {
    "en": {
        "rate": "Too many requests. Please wait a moment.", "large": "Question is too large.",
        "invalid": "Please send a valid question.", "short": "Ask a short product question.",
        "empty": "Tell me your budget and priority: performance, gaming, photography, audio, or portability.",
        "matches": "These verified models are the closest matches for your request.",
    },
    "ka": {
        "rate": "მოთხოვნა მეტისმეტად ხშირია. ცოტა ხნით მოიცადე.", "large": "კითხვა მეტისმეტად დიდია.",
        "invalid": "გამომიგზავნე გამართული კითხვა.", "short": "დასვი მოკლე კითხვა პროდუქტზე.",
        "empty": "მითხარი ბიუჯეტი და მთავარი მიზანი: წარმადობა, გეიმინგი, ფოტო, აუდიო თუ პორტატულობა.",
        "matches": "შენს მოთხოვნას ეს დადასტურებული მოდელები ყველაზე მეტად შეესაბამება.",
    },
    "ru": {
        "rate": "Слишком много запросов. Немного подождите.", "large": "Вопрос слишком большой.",
        "invalid": "Отправьте корректный вопрос.", "short": "Задайте короткий вопрос о товаре.",
        "empty": "Укажите бюджет и приоритет: производительность, игры, фото, аудио или портативность.",
        "matches": "Эти проверенные модели лучше всего соответствуют вашему запросу.",
    },
}

GUIDE_CATEGORY_ALIASES = {
    "smartphones": ("phone", "smartphone", "iphone", "android", "ტელეფონ", "სმარტფონ", "телефон", "смартфон"),
    "laptops": ("laptop", "notebook", "macbook", "ლეპტოპ", "ноутбук"),
    "tablets": ("tablet", "ipad", "ტაბლეტ", "планшет"),
    "cameras": ("camera", "photo", "video", "კამერ", "ფოტო", "камера", "фото"),
    "gaming": ("gaming", "game", "console", "playstation", "xbox", "გეიმ", "თამაშ", "игр", "консоль"),
    "wearables": ("watch", "wearable", "fitness", "საათ", "ფიტნეს", "часы", "фитнес"),
    "graphics-cards": ("gpu", "graphics", "geforce", "radeon", "ვიდეობარათ", "видеокарт"),
    "monitors": ("monitor", "display", "მონიტორ", "монитор"),
    "processors": ("cpu", "processor", "ryzen", "core", "პროცესორ", "процессор"),
    "microphones": ("microphone", "mic", "მიკროფონ", "микрофон"),
    "keyboards": ("keyboard", "კლავიატურ", "клавиатур"),
    "printers": ("printer", "print", "პრინტერ", "принтер"),
    "mice": ("mouse", "მაუს", "мыш"),
}

GUIDE_STOP_WORDS = {
    "the", "and", "for", "with", "want", "need", "show", "best", "good", "under", "budget",
    "და", "რომ", "მინდა", "კარგი", "საუკეთესო", "ბიუჯეტი", "მდე",
    "для", "мне", "нужен", "нужна", "покажи", "лучший", "хороший", "бюджет", "до",
}


def _guide_response_language(message, interface_language):
    """Prefer the shopper's language over the URL locale for AI replies."""
    if re.search(r"[\u10A0-\u10FF]", message):
        return "ka"
    if re.search(r"[\u0400-\u04FF]", message):
        return "ru"
    return interface_language if interface_language in {"en", "ka", "ru"} else "en"


@require_POST
def guide(request):
    language = (get_language() or "en").split("-")[0]
    text = GUIDE_TEXT.get(language, GUIDE_TEXT["en"])
    if cache_rate_limited("guide-ip", request_ip(request), 20, 300):
        return JsonResponse({"reply": text["rate"], "products": []}, status=429)
    if int(request.META.get("CONTENT_LENGTH") or 0) > 4096:
        return JsonResponse({"reply": text["large"], "products": []}, status=413)
    try:
        payload = json.loads(request.body.decode("utf-8"))
        message = str(payload.get("message", "")).strip()
    except (json.JSONDecodeError, UnicodeDecodeError, AttributeError):
        return JsonResponse({"reply": text["invalid"], "products": []}, status=400)
    if not 2 <= len(message) <= 240:
        return JsonResponse({"reply": text["short"], "products": []}, status=400)

    lowered = message.casefold()
    categories = [slug for slug, aliases in GUIDE_CATEGORY_ALIASES.items() if any(alias in lowered for alias in aliases)]
    budget_values = []
    for raw in re.findall(r"(?<!\w)\d[\d\s,.]{1,10}", lowered):
        digits = re.sub(r"\D", "", raw)
        if digits and 100 <= int(digits) <= 100000:
            budget_values.append(int(digits))
    budget = max(budget_values) if budget_values else None

    terms = [
        term for term in re.findall(r"[\w-]+", lowered, flags=re.UNICODE)
        if len(term) >= 2 and term not in GUIDE_STOP_WORDS and not term.isdigit()
    ][:10]
    products = Product.objects.storefront()
    if categories:
        category_query = Q()
        for category_slug in categories:
            category_query |= Q(category__slug__icontains=category_slug)
        products = products.filter(category_query)
    if budget:
        products = products.filter(price__lte=budget)
    query = Q()
    for term in terms:
        query |= (
            Q(name__icontains=term) | Q(name_ka__icontains=term) | Q(name_en__icontains=term)
            | Q(name_ru__icontains=term) | Q(description__icontains=term)
            | Q(short_description__icontains=term) | Q(category__name__icontains=term)
            | Q(category__name_ka__icontains=term) | Q(category__name_ru__icontains=term)
            | Q(brand__icontains=term) | Q(sku__icontains=term)
        )
    if terms:
        matched = products.filter(query)
        if not matched.exists() and (categories or budget):
            matched = products
    else:
        matched = products if categories or budget else Product.objects.none()
    matches = list(matched.order_by("-rating", "price", "name")[:5])
    ai_reply = gemini_guide_reply(
        message=message,
        language=_guide_response_language(message, language),
        products=matches,
    )
    if not matches:
        return JsonResponse({"reply": ai_reply or text["empty"], "products": []})
    return JsonResponse(
        {
            "reply": ai_reply or text["matches"],
            "products": [
                {
                    "name": item.localized_name, "price": str(item.price), "url": item.get_absolute_url(),
                    'brand': item.brand, 'category': item.category.localized_name,
                    'rating': str(item.rating) if item.rating_count else '',
                    'rating_count': item.rating_count,
                    "specs": item.short_description, "image": item.display_image,
                }
                for item in matches
            ],
        }
    )

@require_GET
def robots_txt(request):
    site_url = request.build_absolute_uri("/").rstrip("/")
    return render(request, "robots.txt", {"site_url": site_url}, content_type="text/plain")


@require_GET
def sitemap_xml(request):
    site_url = request.build_absolute_uri("/").rstrip("/")
    return render(
        request,
        "sitemap.xml",
        {
            "site_url": site_url,
            "categories": Category.objects.filter(is_active=True),
            "products": Product.objects.published().only("slug", "updated_at"),
        },
        content_type="application/xml",
    )
