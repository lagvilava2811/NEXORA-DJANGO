import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import get_language
from django.views.decorators.http import require_GET, require_POST

from .models import AccountDeletionRequest, ReturnRequest, WarrantyClaim


logger = logging.getLogger("store.privacy")


LEGAL_PAGES = {
    "en": {
        "privacy": {
            "title": "Privacy notice",
            "intro": "This notice explains what NEXORA stores when you use the shop and how you can exercise your account-data rights.",
            "sections": [
                ("Data we process", "Account identity and contact details, saved delivery addresses, order and support history, wishlist and ratings, security events, and the cookies required for sessions, carts and fraud prevention."),
                ("Why we process it", "To create and secure accounts, fulfil orders, provide support and warranties, prevent abuse, and meet applicable accounting or legal obligations."),
                ("Retention", "Account-only data is removed or anonymised when a valid deletion request is completed. Order, payment, fraud-prevention, warranty or tax records may be retained for the period required by applicable law or an unresolved transaction."),
                ("Your choices", "You can download a machine-readable copy of your account data and submit or cancel a deletion request from your account page. A request is reviewed before fulfillment so legally required order records are not silently destroyed."),
                ("Processors and transfers", "Hosting, email, storage and other processors must be listed here before public launch when those providers are selected. NEXORA does not claim a processor or transfer arrangement that has not been configured."),
            ],
        },
        "terms": {
            "title": "Terms of use and sale",
            "intro": "These baseline terms govern use of the NEXORA storefront. Operator identity, jurisdiction-specific consumer terms and business contact details must be configured before public launch.",
            "sections": [
                ("Accounts", "Keep your credentials confidential and provide accurate contact and delivery information. We may restrict activity that threatens the service or other customers."),
                ("Catalogue and orders", "Product descriptions, prices and availability can be corrected before an order is accepted. Submitting checkout creates an order request; confirmation and payment status determine whether it is accepted."),
                ("Delivery, returns and warranty", "The delivery estimate, return window and warranty shown during checkout or on the product apply together with mandatory consumer rights in the buyer’s jurisdiction."),
                ("Acceptable use", "Do not probe, overload, scrape abusively, bypass access controls, submit malicious content or misuse the guide and account systems."),
                ("Changes and contact", "Material changes should be dated and communicated through the storefront. Operator and legal contact details are displayed below only when configured by the deployer."),
            ],
        },
        "cookies": {
            "title": "Cookie notice",
            "intro": "NEXORA currently uses cookies and browser storage required to operate the storefront; non-essential advertising or analytics cookies are not enabled by this codebase.",
            "sections": [
                ("Necessary storage", "Session and CSRF cookies protect sign-in and forms. Session storage keeps the cart and checkout state. Theme and interface preferences may be stored in the browser."),
                ("Consent", "Strictly necessary storage is used to provide the service and security. If analytics, advertising or other optional trackers are introduced, they must remain disabled until a suitable consent choice is implemented where required."),
                ("Controls", "You can clear site data in your browser, but doing so may sign you out and remove an unsubmitted cart or preferences."),
            ],
        },
    },
    "ka": {
        "privacy": {
            "title": "კონფიდენციალურობის შეტყობინება",
            "intro": "აქ აღწერილია, რა მონაცემებს ინახავს NEXORA მაღაზიის გამოყენებისას და როგორ შეგიძლიათ თქვენი უფლებებით სარგებლობა.",
            "sections": [
                ("რა მონაცემებს ვამუშავებთ", "ანგარიშისა და საკონტაქტო მონაცემებს, მიწოდების მისამართებს, შეკვეთებისა და მხარდაჭერის ისტორიას, სურვილების სიას, შეფასებებს, უსაფრთხოების მოვლენებს და სესიის, კალათისა და თაღლითობის პრევენციისთვის აუცილებელ cookies-ს."),
                ("დამუშავების მიზანი", "ანგარიშის შექმნა და დაცვა, შეკვეთის შესრულება, მხარდაჭერა და გარანტია, ბოროტად გამოყენების პრევენცია და მოქმედი საბუღალტრო თუ სამართლებრივი ვალდებულებების შესრულება."),
                ("შენახვის ვადა", "ანგარიშთან დაკავშირებული მონაცემები იშლება ან ანონიმდება დასაბუთებული მოთხოვნის შესრულებისას. შეკვეთის, გადახდის, თაღლითობის პრევენციის, გარანტიის ან საგადასახადო ჩანაწერები შეიძლება შენარჩუნდეს კანონით მოთხოვნილი ვადით ან მიმდინარე ტრანზაქციის დასრულებამდე."),
                ("თქვენი არჩევანი", "ანგარიშის გვერდიდან შეგიძლიათ ჩამოტვირთოთ თქვენი მონაცემების მანქანურად წაკითხვადი ასლი და გაგზავნოთ ან გააუქმოთ წაშლის მოთხოვნა. მოთხოვნა მოწმდება, რათა კანონით შესანახი შეკვეთის ჩანაწერები ავტომატურად არ განადგურდეს."),
                ("დამმუშავებლები და გადაცემა", "ჰოსტინგის, ელფოსტის, საცავის და სხვა მომწოდებლების სია საჯარო გაშვებამდე უნდა გამოქვეყნდეს მათი არჩევის შემდეგ. დაუკონფიგურირებელ მომწოდებელზე ან მონაცემთა გადაცემაზე NEXORA განცხადებას არ აკეთებს."),
            ],
        },
        "terms": {
            "title": "გამოყენებისა და გაყიდვის პირობები",
            "intro": "ეს არის NEXORA-ს საბაზისო პირობები. საჯარო გაშვებამდე უნდა დაემატოს ოპერატორის იდენტობა, შესაბამისი იურისდიქციის სამომხმარებლო პირობები და რეალური საკონტაქტო მონაცემები.",
            "sections": [
                ("ანგარიში", "დაიცავით ავტორიზაციის მონაცემები და მიუთითეთ ზუსტი საკონტაქტო და მიწოდების ინფორმაცია. სერვისის ან მომხმარებლების საფრთხის შემცველი აქტივობა შეიძლება შეიზღუდოს."),
                ("კატალოგი და შეკვეთა", "პროდუქტის აღწერა, ფასი და ხელმისაწვდომობა შეიძლება გასწორდეს შეკვეთის მიღებამდე. Checkout აგზავნის შეკვეთის მოთხოვნას; მიღებას განსაზღვრავს დადასტურება და გადახდის სტატუსი."),
                ("მიწოდება, დაბრუნება და გარანტია", "Checkout-ზე ან პროდუქტთან ნაჩვენები პირობები მოქმედებს მყიდველის იურისდიქციით მინიჭებულ სავალდებულო უფლებებთან ერთად."),
                ("დასაშვები გამოყენება", "აკრძალულია სისტემის გადატვირთვა, დაცვის გვერდის ავლა, მავნე კონტენტის გაგზავნა და guide/account ფუნქციების ბოროტად გამოყენება."),
                ("ცვლილებები და კავშირი", "მნიშვნელოვან ცვლილებას უნდა ახლდეს თარიღი და შეტყობინება. ოპერატორის მონაცემები ქვემოთ გამოჩნდება მხოლოდ deployment-ში მათი სწორად მითითების შემდეგ."),
            ],
        },
        "cookies": {
            "title": "Cookie-ების შეტყობინება",
            "intro": "NEXORA ამჟამად იყენებს მხოლოდ მაღაზიის მუშაობისთვის აუცილებელ cookies-სა და browser storage-ს; ამ კოდში არასავალდებულო სარეკლამო ან ანალიტიკური cookies ჩართული არ არის.",
            "sections": [
                ("აუცილებელი საცავი", "Session და CSRF cookies იცავს ავტორიზაციასა და ფორმებს. სესია ინახავს კალათასა და checkout-ის მდგომარეობას; თემა და ინტერფეისის არჩევანი შეიძლება ბრაუზერში შეინახოს."),
                ("თანხმობა", "აუცილებელი საცავი გამოიყენება სერვისისა და უსაფრთხოებისთვის. ანალიტიკის, რეკლამის ან სხვა tracker-ის დამატებისას ისინი უნდა დარჩეს გამორთული შესაბამისი თანხმობის მიღებამდე, როცა ამას კანონი მოითხოვს."),
                ("მართვა", "ბრაუზერიდან შეგიძლიათ საიტის მონაცემების გასუფთავება, თუმცა ამით შესაძლოა გამოხვიდეთ ანგარიშიდან და წაიშალოს გაუგზავნელი კალათა ან პარამეტრები."),
            ],
        },
    },
    "ru": {
        "privacy": {
            "title": "Уведомление о конфиденциальности",
            "intro": "Здесь описано, какие данные хранит NEXORA при использовании магазина и как воспользоваться правами в отношении данных аккаунта.",
            "sections": [
                ("Какие данные обрабатываются", "Данные аккаунта и контактов, адреса доставки, история заказов и поддержки, список желаний, оценки, события безопасности и cookies, необходимые для сессий, корзины и предотвращения мошенничества."),
                ("Цели обработки", "Создание и защита аккаунта, выполнение заказов, поддержка и гарантия, предотвращение злоупотреблений и исполнение применимых бухгалтерских или юридических обязанностей."),
                ("Срок хранения", "Данные, относящиеся только к аккаунту, удаляются или обезличиваются после выполнения обоснованного запроса. Записи о заказах, оплате, гарантиях, налогах и предотвращении мошенничества могут храниться в течение установленного законом срока или до завершения операции."),
                ("Ваш выбор", "В аккаунте можно скачать машиночитаемую копию данных, подать или отменить запрос на удаление. Запрос проверяется, чтобы обязательные записи о заказах не удалялись автоматически."),
                ("Обработчики и передача", "Поставщики хостинга, почты, хранения и других услуг должны быть перечислены до публичного запуска после их выбора. NEXORA не заявляет о неподключённых поставщиках или передачах данных."),
            ],
        },
        "terms": {
            "title": "Условия использования и продажи",
            "intro": "Это базовые условия NEXORA. До публичного запуска необходимо указать оператора, применимые потребительские условия и реальные контактные данные.",
            "sections": [
                ("Аккаунты", "Храните учётные данные в тайне и предоставляйте точные контакты и адрес доставки. Действия, угрожающие сервису или покупателям, могут быть ограничены."),
                ("Каталог и заказы", "Описание, цена и наличие могут быть исправлены до принятия заказа. Checkout создаёт запрос на заказ; принятие определяется подтверждением и статусом оплаты."),
                ("Доставка, возврат и гарантия", "Условия на checkout или странице товара применяются вместе с обязательными правами потребителя в юрисдикции покупателя."),
                ("Допустимое использование", "Запрещено перегружать сервис, обходить контроль доступа, отправлять вредоносный контент и злоупотреблять функциями guide или аккаунта."),
                ("Изменения и контакты", "Существенные изменения должны датироваться и сообщаться через магазин. Данные оператора отображаются ниже только после настройки при развёртывании."),
            ],
        },
        "cookies": {
            "title": "Уведомление о cookies",
            "intro": "Сейчас NEXORA использует cookies и хранилище браузера, необходимые для работы магазина; необязательные рекламные или аналитические cookies этим кодом не включены.",
            "sections": [
                ("Необходимое хранение", "Session- и CSRF-cookies защищают вход и формы. Сессия хранит корзину и состояние checkout; тема и настройки интерфейса могут храниться в браузере."),
                ("Согласие", "Строго необходимое хранение используется для сервиса и безопасности. При добавлении аналитики, рекламы или иных trackers они должны быть выключены до получения надлежащего согласия, когда оно требуется."),
                ("Управление", "Данные сайта можно очистить в браузере, но это может завершить сеанс и удалить неотправленную корзину или настройки."),
            ],
        },
    },
}


def _language():
    language = (get_language() or "en").split("-")[0]
    return language if language in LEGAL_PAGES else "en"


@require_GET
def legal_page(request, document):
    page = LEGAL_PAGES[_language()].get(document)
    if page is None:
        from django.http import Http404
        raise Http404
    return render(request, "legal.html", {
        "page": page,
        "document": document,
        "legal_name": getattr(settings, "NEXORA_LEGAL_NAME", ""),
        "legal_address": getattr(settings, "NEXORA_LEGAL_ADDRESS", ""),
        "support_email": getattr(settings, "NEXORA_SUPPORT_EMAIL", ""),
    })


def _iso(value):
    return value.isoformat() if value else None


@login_required(login_url="login")
@require_GET
def account_data_export(request):
    user = request.user
    orders = user.orders.prefetch_related("items__product", "items__variant").order_by("created_at")
    payload = {
        "generated_at": timezone.now().isoformat(),
        "account": {
            "username": user.get_username(),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "date_joined": _iso(user.date_joined),
            "last_login": _iso(user.last_login),
        },
        "addresses": list(user.addresses.values("title", "full_name", "phone", "city", "address_line", "postal_code", "is_default")),
        "orders": [
            {
                "reference": order.reference,
                "status": order.status,
                "payment_status": order.payment_status,
                "payment_method": order.payment_method,
                "full_name": order.full_name,
                "email": order.email,
                "phone": order.phone,
                "address": order.address,
                "city": order.city,
                "postal_code": order.postal_code,
                "subtotal": str(order.subtotal),
                "shipping_cost": str(order.shipping_cost),
                "tax_amount": str(order.tax_amount),
                "discount_amount": str(order.discount_amount),
                "total": str(order.total),
                "created_at": _iso(order.created_at),
                "items": [
                    {
                        "product": item.product.name,
                        "sku": item.product.sku,
                        "variant": item.variant.name if item.variant else None,
                        "quantity": item.quantity,
                        "unit_price": str(item.unit_price),
                    }
                    for item in order.items.all()
                ],
            }
            for order in orders
        ],
        "wishlist": list(user.wishlists.select_related("product").values("product__name", "product__sku", "created_at")),
        "reviews": list(user.reviews.values("product__name", "rating", "title", "body", "is_approved", "created_at")),
        "ratings": list(user.product_ratings.values("product__name", "rating", "created_at", "updated_at")),
        "returns": list(ReturnRequest.objects.filter(user=user).values("order__reference", "reason", "description", "status", "created_at")),
        "warranty_claims": list(WarrantyClaim.objects.filter(user=user).values("order__reference", "product__name", "description", "status", "created_at")),
    }
    response = JsonResponse(payload, json_dumps_params={"ensure_ascii": False, "indent": 2})
    response["Content-Disposition"] = 'attachment; filename="nexora-account-data.json"'
    response["Cache-Control"] = "no-store, private"
    logger.info("account data exported", extra={"event": "account_data_export", "user_id": user.pk})
    return response


ACCOUNT_MESSAGES = {
    "en": {"requested": "Your deletion request was recorded for review.", "cancelled": "Your deletion request was cancelled."},
    "ka": {"requested": "ანგარიშის წაშლის მოთხოვნა მიღებულია და შემოწმდება.", "cancelled": "ანგარიშის წაშლის მოთხოვნა გაუქმებულია."},
    "ru": {"requested": "Запрос на удаление аккаунта принят на рассмотрение.", "cancelled": "Запрос на удаление аккаунта отменён."},
}


@login_required(login_url="login")
@require_POST
def request_account_deletion(request):
    record, _ = AccountDeletionRequest.objects.get_or_create(user=request.user)
    if record.status != "completed":
        record.status = "pending"
        record.requested_at = timezone.now()
        record.completed_at = None
        record.save(update_fields=("status", "requested_at", "completed_at", "updated_at"))
        logger.info("account deletion requested", extra={"event": "account_deletion_requested", "user_id": request.user.pk})
    messages.success(request, ACCOUNT_MESSAGES[_language()]["requested"])
    return redirect("cabinet")


@login_required(login_url="login")
@require_POST
def cancel_account_deletion(request):
    updated = AccountDeletionRequest.objects.filter(user=request.user, status="pending").update(
        status="cancelled", updated_at=timezone.now(),
    )
    if updated:
        logger.info("account deletion cancelled", extra={"event": "account_deletion_cancelled", "user_id": request.user.pk})
    messages.success(request, ACCOUNT_MESSAGES[_language()]["cancelled"])
    return redirect("cabinet")
