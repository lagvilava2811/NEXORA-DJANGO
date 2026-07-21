from django.utils.translation import get_language
from django.db.models import Count, Q
from .models import Category, Product

COPIES = {
    "en": {
        "brand": "NEXORA",
        "title_tag": "Future, now.",
        "explore": "EXPLORE ALL TECH",
        "items_online": "DEVICES ONLINE",
        "scroll_to_explore": "SCROLL TO EXPLORE",
        "shop_by_category": "SHOP BY CATEGORY",
        "drop_title": "Power without the noise.",
        "drop_subtitle": "New processors. Brighter displays. Gear built to disappear into your day.",
        "explore_computing": "Explore computing",
        "trending_now": "TRENDING NOW",
        "picked_for_you": "Picked for you.",
        "view_all_products": "View all products",
        "signal_eyebrow": "SIGNAL / NEXORA MEMBERS",
        "signal_title": "Be first for the<br><em>next thing.</em>",
        "join_signal": "JOIN THE SIGNAL",
        
        "currency_symbol": "₾",
        "add_to_bag": "ADD TO BAG",
        "in_stock": "In Stock",
        "items": "items",
        "out_of_stock": "Out of Stock",
        "quantity": "Quantity",
        "shipping_info": "Shipping & Delivery",
        "shipping_desc": "Delivery takes 1-2 business days in Tbilisi, 2-4 days worldwide.",
        "returns_info": "Returns",
        "returns_desc": "Free returns within 14 days of delivery.",
        
        "bag": "Bag",
        "update": "Update",
        "bag_empty": "Your selection is empty.",
        "continue_shopping": "Continue shopping",
        "shipping": "Shipping",
        "free": "Free",
        "total": "Total",
        "checkout": "CHECKOUT",
        
        "shop": "Shop",
        "archive_eyebrow": "NEXORA CATALOG",
        "pieces": "devices",
        "collection_title": "THE<br>CATALOG.",
        "search_placeholder": "Search devices...",
        "search": "Search",
        "filter_by_world": "FILTER BY CATEGORY",
        "all_objects": "All products",
        "of": "of",
        "curated_tagline": "CURATED, NOT CLUTTERED",
        "previous": "Previous",
        "next": "Next",
        "intro_eyebrow": "FUTURE IS IN STOCK",
        "hero_title": "Technology<br>that <em>moves</em><br>with you.",
        "hero_subtitle": "Devices selected for performance, designed for the way you actually live.",
        "search_label": "Search tech",
        "order_confirmed": "ORDER CONFIRMED",
        "on_the_list": "You're on the list.",
        "order_success_desc_1": "Order",
        "order_success_desc_2": "is confirmed. We'll send the delivery details to",
        "keep_exploring": "KEEP EXPLORING",
        "reviews": "reviews",
        "variants": "Variants",
        "add_to_wishlist": "Add to Wishlist",
        "add_to_compare": "Add to Compare",
        "specifications": "SPECIFICATIONS",
        "brand_label": "Brand",
        "warranty_label": "Warranty",
        "months_label": "Months",
        "reviews_and_ratings": "REVIEWS & RATINGS",
        "verified_purchase": "Verified Purchase",
        "no_reviews": "No reviews yet. Be the first to share your thoughts!",
        "write_review": "WRITE A REVIEW",
        "rating_label": "Rating:",
        "review_title_placeholder": "Review Title",
        "review_body_placeholder": "Your review...",
        "submit_review": "Submit Review",
        "login_btn": "Log in",
        "to_write_review": "to write a review.",
        "related_devices": "COMPATIBLE / RELATED DEVICES",
        "discover_related": "DISCOVER COMPATIBLE ACCESSORIES AND UPGRADES",
        "your_selection": "YOUR SELECTION",
        "secure_checkout": "SECURE CHECKOUT",
        "complete_order": "Complete your order.",
        "select_saved_address": "Select Saved Address",
        "checkout_login_prompt": "Already have an account? Log in to use saved addresses.",
        "full_name": "Full name",
        "email": "Email",
        "delivery_address": "Delivery address",
        "place_order": "PLACE ORDER",
        "order_summary": "Order Summary",
        "qty_label": "Qty",
        "subtotal": "Subtotal",
        "discount_label": "Discount",
        "promo_code": "Promotional Code",
        "enter_coupon_placeholder": "Enter coupon code",
        "apply_btn": "Apply",
        "coupon_success_1": "Coupon",
        "coupon_success_2": "applied successfully!"
    },
    "ka": {
        "brand": "NEXORA",
        "title_tag": "ტექნოლოგიები მომავლიდან",
        "explore": "აღმოაჩინე კოლექცია",
        "items_online": "ტექნიკა საწყობშია",
        "scroll_to_explore": "ჩამოსქროლე სანახავად",
        "shop_by_category": "იყიდე კატეგორიით",
        "drop_title": "სიმძლავრე ხმაურის გარეშე.",
        "drop_subtitle": "ახალი პროცესორები. უფრო კაშკაშა ეკრანები. ტექნიკა, რომელიც თქვენს დღეს ერგება.",
        "explore_computing": "იხილეთ კომპიუტერები",
        "trending_now": "ამჟამად პოპულარული",
        "picked_for_you": "შერჩეული თქვენთვის.",
        "view_all_products": "ყველა პროდუქტის ნახვა",
        "signal_eyebrow": "SIGNAL / NEXORA-ს წევრები",
        "signal_title": "იყავი პირველი,<br>ვინც გაიგებს <em>სიახლეს.</em>",
        "join_signal": "გაწევრიანდი",
        
        "currency_symbol": "₾",
        "add_to_bag": "კალათაში დამატება",
        "in_stock": "მარაგშია",
        "items": "ცალი",
        "out_of_stock": "ამოიწურა",
        "quantity": "რაოდენობა",
        "shipping_info": "მიწოდების პირობები",
        "shipping_desc": "მიწოდება ხდება 1-2 სამუშაო დღეში თბილისში, 2-4 დღეში მთელ საქართველოში.",
        "returns_info": "დაბრუნება",
        "returns_desc": "დაბრუნება უფასოა მიწოდებიდან 14 დღის განმავლობაში.",
        
        "bag": "კალათა",
        "update": "განახლება",
        "bag_empty": "თქვენი კალათა ცარიელია.",
        "continue_shopping": "მაღაზიაში დაბრუნება",
        "shipping": "მიწოდება",
        "free": "უფასო",
        "total": "სულ",
        "checkout": "შეკვეთის გაფორმება",
        
        "shop": "მაღაზია",
        "archive_eyebrow": "NEXORA კატალოგი",
        "pieces": "პროდუქტი",
        "collection_title": "სრული<br>კატალოგი.",
        "search_placeholder": "მოძებნე ტექნიკა...",
        "search": "ძებნა",
        "filter_by_world": "გაფილტრე კატეგორიით",
        "all_objects": "ყველა პროდუქტი",
        "of": "-",
        "curated_tagline": "შერჩეული ხარისხი",
        "previous": "წინა",
        "next": "შემდეგი",
        "intro_eyebrow": "ტექნოლოგიები მომავლიდან",
        "hero_title": "ტექნოლოგიები,<br>რომლებიც თქვენს <em>რიტმს</em><br>ყვება.",
        "hero_subtitle": "შესრულებისთვის შერჩეული მოწყობილობები, შექმნილი თქვენი ყოველდღიურობისთვის.",
        "search_label": "მოძებნე ტექნიკა",
        "order_confirmed": "შეკვეთა დადასტურებულია",
        "on_the_list": "თქვენ სიაში ხართ.",
        "order_success_desc_1": "შეკვეთა",
        "order_success_desc_2": "დადასტურებულია. მიწოდების დეტალებს გამოგიგზავნით ელ-ფოსტაზე:",
        "keep_exploring": "გააგრძელე ძებნა",
        "reviews": "შეფასება",
        "variants": "ვარიანტები",
        "add_to_wishlist": "სასურველ სიას დამატება",
        "add_to_compare": "შედარება",
        "specifications": "სპეციფიკაციები",
        "brand_label": "ბრენდი",
        "warranty_label": "გარანტია",
        "months_label": "თვე",
        "reviews_and_ratings": "შეფასებები და რეიტინგი",
        "verified_purchase": "დასტურებული შენაძენი",
        "no_reviews": "შეფასებები ჯერ არ არის. იყავი პირველი!",
        "write_review": "დაწერე შეფასება",
        "rating_label": "რეიტინგი:",
        "review_title_placeholder": "შეფასების სათაური",
        "review_body_placeholder": "თქვენი შეფასება...",
        "submit_review": "გაგზავნა",
        "login_btn": "შედით სისტემაში",
        "to_write_review": "შეფასების დასაწერად.",
        "related_devices": "თავსებადი / მსგავსი მოწყობილობები",
        "discover_related": "აღმოაჩინე თავსებადი აქსესუარები და განახლებები",
        "your_selection": "თქვენი არჩევანი",
        "secure_checkout": "უსაფრთხო შეკვეთა",
        "complete_order": "დაასრულეთ თქვენი შეკვეთა.",
        "select_saved_address": "აირჩიეთ შენახული მისამართი",
        "checkout_login_prompt": "უკვე გაქვთ ანგარიში? შედით მისამართების გამოსაყენებლად.",
        "full_name": "სრული სახელი",
        "email": "ელ-ფოსტა",
        "delivery_address": "მიწოდების მისამართი",
        "place_order": "შეკვეთის გაფორმება",
        "order_summary": "შეკვეთის დეტალები",
        "qty_label": "რაოდ.",
        "subtotal": "ჯამი",
        "discount_label": "ფასდაკლება",
        "promo_code": "პრომო კოდი",
        "enter_coupon_placeholder": "შეიყვანეთ კოდი",
        "apply_btn": "გამოყენება",
        "coupon_success_1": "კუპონი",
        "coupon_success_2": "წარმატებით გააქტიურდა!"
    },
    "ru": {
        "brand": "NEXORA",
        "title_tag": "Технологии будущего",
        "explore": "ИССЛЕДОВАТЬ КОЛЛЕКЦИЮ",
        "items_online": "ПРОДУКТОВ ДОСТУПНО",
        "scroll_to_explore": "ПРОКРУТИТЕ ДЛЯ ОБЗОРА",
        "shop_by_category": "КАТЕГОРИИ",
        "drop_title": "Мощность без шума.",
        "drop_subtitle": "Новые процессоры. Яркие дисплеи. Техника, созданная дополнять ваш день.",
        "explore_computing": "Смотреть компьютеры",
        "trending_now": "ПОПУЛЯРНОЕ",
        "picked_for_you": "Специально для вас.",
        "view_all_products": "Смотреть все продукты",
        "signal_eyebrow": "SIGNAL / УЧАСТНИКИ NEXORA",
        "signal_title": "Узнавайте первыми о<br><em>новинках.</em>",
        "join_signal": "ВСТУПИТЬ В КЛУБ",
        
        "currency_symbol": "₾",
        "add_to_bag": "В КОРЗИНУ",
        "in_stock": "В наличии",
        "items": "шт.",
        "out_of_stock": "Нет в наличии",
        "quantity": "Количество",
        "shipping_info": "Доставка",
        "shipping_desc": "Доставка занимает 1-2 рабочих дня по Тбилиси, 2-4 дня по всему миру.",
        "returns_info": "Возврат",
        "returns_desc": "Бесплатный возврат в течение 14 дней с момента доставки.",
        
        "bag": "Корзина",
        "update": "Обновить",
        "bag_empty": "Ваша корзина пуста.",
        "continue_shopping": "Вернуться к покупкам",
        "shipping": "Доставка",
        "free": "Бесплатно",
        "total": "Итого",
        "checkout": "ОФОРМИТЬ ЗАКАЗ",
        
        "shop": "Магазин",
        "archive_eyebrow": "КАТАЛОГ NEXORA",
        "pieces": "товаров",
        "collection_title": "ВЕСЬ<br>КАТАЛОГ.",
        "search_placeholder": "Поиск устройств...",
        "search": "Найти",
        "filter_by_world": "ФИЛЬТР ПО КАТЕГОРИЯМ",
        "all_objects": "Все продукты",
        "of": "из",
        "curated_tagline": "КУРИРУЕМЫЙ ВЫБОР",
        "previous": "Назад",
        "next": "Вперед",
        "intro_eyebrow": "ТЕХНОЛОГИИ БУДУЩЕГО",
        "hero_title": "Технологии,<br>которые двигаются<br><em>вместе с вами.</em>",
        "hero_subtitle": "Устройства, выбранные за производительность и созданные для реальной жизни.",
        "search_label": "Поиск техники",
        "order_confirmed": "ЗАКАЗ ПОДТВЕРЖДЕН",
        "on_the_list": "Вы в списке.",
        "order_success_desc_1": "Заказ",
        "order_success_desc_2": "подтвержден. Мы отправим детали доставки на",
        "keep_exploring": "ПРОДОЛЖИТЬ ОБЗОР",
        "reviews": "отзывов",
        "variants": "Варианты",
        "add_to_wishlist": "В список желаний",
        "add_to_compare": "Сравнить",
        "specifications": "ХАРАКТЕРИСТИКИ",
        "brand_label": "Бренд",
        "warranty_label": "Гарантия",
        "months_label": "мес.",
        "reviews_and_ratings": "ОТЗЫВЫ И РЕЙТИНГ",
        "verified_purchase": "Проверенная покупка",
        "no_reviews": "Отзывов пока нет. Будьте первым!",
        "write_review": "НАПИСАТЬ ОТЗЫВ",
        "rating_label": "Рейтинг:",
        "review_title_placeholder": "Заголовок отзыва",
        "review_body_placeholder": "Ваш отзыв...",
        "submit_review": "Отправить отзыв",
        "login_btn": "Войдите",
        "to_write_review": "чтобы написать отзыв.",
        "related_devices": "СОВМЕСТИМЫЕ / ПОХОЖИЕ УСТРОЙСТВА",
        "discover_related": "ОТКРОЙТЕ СОВМЕСТИМЫЕ АКСЕССУАРЫ И ОБНОВЛЕНИЯ",
        "your_selection": "ВАШ ВЫБОР",
        "secure_checkout": "БЕЗОПАСНЫЙ ЗАКАЗ",
        "complete_order": "Завершите ваш заказ.",
        "select_saved_address": "Выберите сохраненный адрес",
        "checkout_login_prompt": "Уже есть аккаунт? Войдите, чтобы использовать сохраненные адреса.",
        "full_name": "Полное имя",
        "email": "Email",
        "delivery_address": "Адрес доставки",
        "place_order": "ОФОРМИТЬ ЗАКАЗ",
        "order_summary": "Детали заказа",
        "qty_label": "Кол-во",
        "subtotal": "Подытог",
        "discount_label": "Скидка",
        "promo_code": "Промокод",
        "enter_coupon_placeholder": "Введите промокод",
        "apply_btn": "Применить",
        "coupon_success_1": "Купон",
        "coupon_success_2": "успешно применен!"
    }
}

EXTRA_COPIES = {
    "en": {
        "meta_description": "NEXORA — verified technology, exact product media, transparent provenance and secure checkout.",
        "skip_content": "Skip to content", "main_navigation": "Main navigation", "open_menu": "Open menu",
        "switch_theme": "Switch color theme", "theme_light": "Light theme", "theme_dark": "Dark theme",
        "account": "Account", "log_in": "Log in", "log_out": "Log out", "open_bag": "Open bag",
        "close_bag": "Close bag", "bag_summary": "Shopping bag", "close": "Close",
        "guide_label": "NEXORA shopping guide", "guide_open": "Ask NEXORA", "guide_close": "Close guide",
        "guide_intro": "Ask about performance, budget, gaming, photography, audio, or portability.",
        "guide_prompt": "What are you shopping for?", "guide_placeholder": "e.g. a camera for travel", "send": "Send",
        "footer_tagline": "Verified technology, made personal.", "delivery_returns": "Delivery & returns", "support": "Support",
        "brand_filter": "Brand", "price_range": "Price range", "min_price": "Minimum price", "max_price": "Maximum price",
        "apply": "Apply", "clear_brand": "Clear brand", "min_rating": "Minimum rating", "stock_only": "In stock only",
        "featured": "Featured", "newest": "Newest", "price_low": "Price low to high", "price_high": "Price high to low",
        "top_rated": "Top rated", "no_results": "No verified products match these filters.",
        "phone": "Phone", "city": "City", "postal_code": "Postal code", "payment_method": "Payment method",
        "notes": "Order notes", "accept_terms": "I accept the terms and return policy", "form_errors": "Please correct the highlighted fields.",
        "video_pause": "Pause background video", "video_play": "Play background video", "verified_media": "Verified local media",
        "menu": "Menu", "remove": "Remove", "decrease_quantity": "Decrease quantity", "increase_quantity": "Increase quantity"
    },
    "ka": {
        "meta_description": "NEXORA — დადასტურებული ტექნიკა, რეალური პროდუქტის ფოტოები, გამჭვირვალე წყაროები და უსაფრთხო შეკვეთა.",
        "skip_content": "კონტენტზე გადასვლა", "main_navigation": "მთავარი ნავიგაცია", "open_menu": "მენიუს გახსნა",
        "switch_theme": "ფერის თემის შეცვლა", "theme_light": "ღია თემა", "theme_dark": "მუქი თემა",
        "account": "ანგარიში", "log_in": "შესვლა", "log_out": "გასვლა", "open_bag": "კალათის გახსნა",
        "close_bag": "კალათის დახურვა", "bag_summary": "საყიდლების კალათა", "close": "დახურვა",
        "guide_label": "NEXORA-ს სავაჭრო მეგზური", "guide_open": "ჰკითხე NEXORA-ს", "guide_close": "მეგზურის დახურვა",
        "guide_intro": "ჰკითხე წარმადობაზე, ბიუჯეტზე, გეიმინგზე, ფოტოზე, აუდიოზე ან პორტაბელურობაზე.",
        "guide_prompt": "რას ეძებ?", "guide_placeholder": "მაგ. კამერა მოგზაურობისთვის", "send": "გაგზავნა",
        "footer_tagline": "დადასტურებული ტექნოლოგია, შენზე მორგებული.", "delivery_returns": "მიწოდება და დაბრუნება", "support": "დახმარება",
        "brand_filter": "ბრენდი", "price_range": "ფასის დიაპაზონი", "min_price": "მინიმალური ფასი", "max_price": "მაქსიმალური ფასი",
        "apply": "გამოყენება", "clear_brand": "ბრენდის გასუფთავება", "min_rating": "მინიმალური რეიტინგი", "stock_only": "მხოლოდ მარაგში",
        "featured": "რჩეული", "newest": "უახლესი", "price_low": "ფასი ზრდადობით", "price_high": "ფასი კლებადობით",
        "top_rated": "საუკეთესო შეფასება", "no_results": "ამ ფილტრებით დადასტურებული პროდუქტი ვერ მოიძებნა.",
        "phone": "ტელეფონი", "city": "ქალაქი", "postal_code": "საფოსტო ინდექსი", "payment_method": "გადახდის მეთოდი",
        "notes": "შეკვეთის შენიშვნა", "accept_terms": "ვეთანხმები პირობებსა და დაბრუნების პოლიტიკას", "form_errors": "გთხოვ, გაასწორო მონიშნული ველები.",
        "video_pause": "ფონის ვიდეოს შეჩერება", "video_play": "ფონის ვიდეოს გაშვება", "verified_media": "დადასტურებული ლოკალური მედია",
        "menu": "მენიუ", "remove": "წაშლა", "decrease_quantity": "რაოდენობის შემცირება", "increase_quantity": "რაოდენობის გაზრდა"
    },
    "ru": {
        "meta_description": "NEXORA — проверенная техника, реальные фото товаров, прозрачные источники и безопасное оформление заказа.",
        "skip_content": "Перейти к содержимому", "main_navigation": "Основная навигация", "open_menu": "Открыть меню",
        "switch_theme": "Переключить тему", "theme_light": "Светлая тема", "theme_dark": "Тёмная тема",
        "account": "Аккаунт", "log_in": "Войти", "log_out": "Выйти", "open_bag": "Открыть корзину",
        "close_bag": "Закрыть корзину", "bag_summary": "Корзина", "close": "Закрыть",
        "guide_label": "Помощник NEXORA", "guide_open": "Спросить NEXORA", "guide_close": "Закрыть помощника",
        "guide_intro": "Спросите о производительности, бюджете, играх, фото, аудио или портативности.",
        "guide_prompt": "Что вы ищете?", "guide_placeholder": "например, камера для путешествий", "send": "Отправить",
        "footer_tagline": "Проверенные технологии, выбранные для вас.", "delivery_returns": "Доставка и возврат", "support": "Поддержка",
        "brand_filter": "Бренд", "price_range": "Диапазон цен", "min_price": "Минимальная цена", "max_price": "Максимальная цена",
        "apply": "Применить", "clear_brand": "Сбросить бренд", "min_rating": "Минимальный рейтинг", "stock_only": "Только в наличии",
        "featured": "Рекомендуемые", "newest": "Новинки", "price_low": "Цена по возрастанию", "price_high": "Цена по убыванию",
        "top_rated": "Лучший рейтинг", "no_results": "По этим фильтрам проверенные товары не найдены.",
        "phone": "Телефон", "city": "Город", "postal_code": "Почтовый индекс", "payment_method": "Способ оплаты",
        "notes": "Комментарий к заказу", "accept_terms": "Я принимаю условия и правила возврата", "form_errors": "Исправьте выделенные поля.",
        "video_pause": "Приостановить фоновое видео", "video_play": "Воспроизвести фоновое видео", "verified_media": "Проверенное локальное медиа",
        "menu": "Меню", "remove": "Удалить", "decrease_quantity": "Уменьшить количество", "increase_quantity": "Увеличить количество"
    },
}
for language, values in EXTRA_COPIES.items():
    COPIES[language].update(values)
CATEGORY_TRANSLATIONS = {
    "ka": {
        "Smartphones": "სმარტფონები",
        "Computing": "კომპიუტერები",
        "Gaming": "გეიმინგი",
        "Audio": "აუდიო",
        "Wearables": "აქსესუარები",
        "Smart Home": "ჭკვიანი სახლი",
        "Apparel": "ტანსაცმელი",
        "Objects": "ობიექტები",
        "Editions": "გამოცემები",
    },
    "ru": {
        "Smartphones": "Смартфоны",
        "Computing": "Компьютеры",
        "Gaming": "Гейминг",
        "Audio": "Аудио",
        "Wearables": "Аксессуары",
        "Smart Home": "Умный дом",
        "Apparel": "Одежда",
        "Objects": "Предметы",
        "Editions": "Издания",
    }
}

def global_context(request):
    lang = get_language()
    copy = COPIES.get(lang, COPIES["en"])
    
    bag = request.session.get("bag", {})
    bag_total_count = 0
    if isinstance(bag, dict):
        for qty in bag.values():
            try:
                bag_total_count += int(qty)
            except (ValueError, TypeError):
                pass
                
    # Fetch active categories and translate them dynamically
    categories = list(Category.objects.filter(is_active=True).annotate(published_count=Count("products", filter=Q(products__is_published=True, products__is_active=True), distinct=True)).order_by("display_order", "name"))
    for c in categories:
        local_name = getattr(c, f"name_{lang}", "")
        if not local_name and lang in CATEGORY_TRANSLATIONS:
            local_name = CATEGORY_TRANSLATIONS[lang].get(c.name, "")
        if local_name:
            c.name = local_name

    # Generate correct localized URLs for the language switcher
    path = request.path
    clean_path = path
    for l in ["en", "ru"]:
        if path.startswith(f"/{l}/"):
            clean_path = path[3:]
            break
        elif path == f"/{l}":
            clean_path = "/"
            break
            
    if not clean_path.startswith("/"):
        clean_path = "/" + clean_path
        
    lang_urls = {
        "ka": clean_path,
        "en": f"/en{clean_path}" if clean_path != "/" else "/en/",
        "ru": f"/ru{clean_path}" if clean_path != "/" else "/ru/",
    }
    
    # Keep query parameters if they exist
    query_string = request.META.get('QUERY_STRING', '')
    if query_string:
        for lkey in lang_urls:
            lang_urls[lkey] = f"{lang_urls[lkey]}?{query_string}"
            
    return {
        "copy": copy,
        "bag_count": bag_total_count,
        "global_categories": categories,
        "lang_urls": lang_urls,
        "global_products_count": Product.objects.published().count(),
        "csp_nonce": getattr(request, "csp_nonce", ""),
    }

ACCOUNT_COPIES = {
    "en": {
        "home_label": "NEXORA home", "new_badge": "New", "source_link": "Wikimedia source",
        "account_eyebrow": "NEXORA ACCOUNT", "create_account": "Create account", "create_account_action": "Create account",
        "create_account_prompt": "Create a NEXORA account", "orders_title": "Orders", "addresses_title": "Addresses",
        "no_addresses": "No saved addresses.", "save_address": "Save address", "wishlist_title": "Wishlist",
        "service_title": "Returns & warranty", "return_label": "Return", "warranty_claim_label": "Warranty",
        "no_service_requests": "No active service requests.", "compare_title": "Compare devices", "compare_eyebrow": "NEXORA COMPARE",
        "comparison_label": "Product comparison", "feature_label": "Feature", "rating": "Rating",
        "footer_location": "TBILISI / GEORGIA", "email_in_use": "An account already uses this email address."
    },
    "ka": {
        "home_label": "NEXORA-ს მთავარი გვერდი", "new_badge": "ახალი", "source_link": "Wikimedia-ს წყარო",
        "account_eyebrow": "NEXORA ანგარიში", "create_account": "ანგარიშის შექმნა", "create_account_action": "ანგარიშის შექმნა",
        "create_account_prompt": "შექმენი NEXORA ანგარიში", "orders_title": "შეკვეთები", "addresses_title": "მისამართები",
        "no_addresses": "შენახული მისამართები არ არის.", "save_address": "მისამართის შენახვა", "wishlist_title": "სურვილების სია",
        "service_title": "დაბრუნება და გარანტია", "return_label": "დაბრუნება", "warranty_claim_label": "გარანტია",
        "no_service_requests": "აქტიური მომსახურების მოთხოვნა არ არის.", "compare_title": "მოწყობილობების შედარება", "compare_eyebrow": "NEXORA შედარება",
        "comparison_label": "პროდუქტების შედარება", "feature_label": "მახასიათებელი", "rating": "რეიტინგი",
        "footer_location": "თბილისი / საქართველო", "email_in_use": "ამ ელფოსტით ანგარიში უკვე არსებობს."
    },
    "ru": {
        "home_label": "Главная NEXORA", "new_badge": "Новинка", "source_link": "Источник Wikimedia",
        "account_eyebrow": "АККАУНТ NEXORA", "create_account": "Создать аккаунт", "create_account_action": "Создать аккаунт",
        "create_account_prompt": "Создать аккаунт NEXORA", "orders_title": "Заказы", "addresses_title": "Адреса",
        "no_addresses": "Сохранённых адресов нет.", "save_address": "Сохранить адрес", "wishlist_title": "Избранное",
        "service_title": "Возвраты и гарантия", "return_label": "Возврат", "warranty_claim_label": "Гарантия",
        "no_service_requests": "Активных обращений нет.", "compare_title": "Сравнение устройств", "compare_eyebrow": "СРАВНЕНИЕ NEXORA",
        "comparison_label": "Сравнение товаров", "feature_label": "Характеристика", "rating": "Рейтинг",
        "footer_location": "ТБИЛИСИ / ГРУЗИЯ", "email_in_use": "Аккаунт с этим адресом электронной почты уже существует."
    },
}
for language, values in ACCOUNT_COPIES.items():
    COPIES[language].update(values)
ACTION_COPIES = {
    "en": {"address_saved": "Address saved.", "address_error": "Please correct the address fields.", "address_removed": "Address removed.", "coupon_applied": "Coupon applied.", "coupon_invalid": "This coupon is invalid for the current bag."},
    "ka": {"address_saved": "მისამართი შენახულია.", "address_error": "გთხოვ, გაასწორო მისამართის მონიშნული ველები.", "address_removed": "მისამართი წაიშალა.", "coupon_applied": "კუპონი გააქტიურდა.", "coupon_invalid": "ეს კუპონი მიმდინარე კალათისთვის არ მოქმედებს."},
    "ru": {"address_saved": "Адрес сохранён.", "address_error": "Исправьте отмеченные поля адреса.", "address_removed": "Адрес удалён.", "coupon_applied": "Промокод применён.", "coupon_invalid": "Этот промокод не подходит для текущей корзины."},
}
for language, values in ACTION_COPIES.items():
    COPIES[language].update(values)
ASYNC_COPIES = {
    "en": {"cart_load_error": "Unable to load bag.", "cart_update_error": "Unable to update bag.", "cart_add_error": "Unable to add product.", "product_added": "Product added to bag.", "guide_unable": "I could not answer that yet.", "connection_error": "Connection error. Please try again."},
    "ka": {"cart_load_error": "კალათის ჩატვირთვა ვერ მოხერხდა.", "cart_update_error": "კალათის განახლება ვერ მოხერხდა.", "cart_add_error": "პროდუქტის დამატება ვერ მოხერხდა.", "product_added": "პროდუქტი კალათაში დაემატა.", "guide_unable": "ამ კითხვაზე პასუხი ჯერ ვერ მოვამზადე.", "connection_error": "კავშირის შეცდომა. სცადე თავიდან."},
    "ru": {"cart_load_error": "Не удалось загрузить корзину.", "cart_update_error": "Не удалось обновить корзину.", "cart_add_error": "Не удалось добавить товар.", "product_added": "Товар добавлен в корзину.", "guide_unable": "Пока не удалось ответить на этот вопрос.", "connection_error": "Ошибка соединения. Попробуйте ещё раз."},
}
for language, values in ASYNC_COPIES.items():
    COPIES[language].update(values)
A11Y_COPIES = {
    "en": {"breadcrumb": "Breadcrumb", "product_gallery": "Product gallery", "rating_out_of": "Rating {rating} out of 5"},
    "ka": {"breadcrumb": "ნავიგაციის გზა", "product_gallery": "პროდუქტის გალერეა", "rating_out_of": "რეიტინგი {rating} ხუთიდან"},
    "ru": {"breadcrumb": "Навигационная цепочка", "product_gallery": "Галерея товара", "rating_out_of": "Рейтинг {rating} из 5"},
}
for language, values in A11Y_COPIES.items():
    COPIES[language].update(values)
REVIEW_COPIES = {
    "en": {"review_submitted": "Your review was submitted for moderation.", "review_error": "Please correct the review fields."},
    "ka": {"review_submitted": "შეფასება მოდერაციაზე გაიგზავნა.", "review_error": "გთხოვ, გაასწორო შეფასების მონიშნული ველები."},
    "ru": {"review_submitted": "Отзыв отправлен на модерацию.", "review_error": "Исправьте отмеченные поля отзыва."},
}
for language, values in REVIEW_COPIES.items():
    COPIES[language].update(values)

RATING_COPIES = {
    'en': {
        'rate_product': 'Rate this product', 'your_rating': 'Your rating',
        'ratings': 'ratings', 'save_rating': 'Save rating', 'rating_saved': 'Rating saved.',
        'rating_invalid': 'Choose a rating from 1 to 5.',
        'rating_login_required': 'Log in to rate this product.', 'sign_in_to_rate': 'Log in to leave a rating.',
    },
    'ka': {
        'rate_product': 'შეაფასე პროდუქტი', 'your_rating': 'შენი შეფასება',
        'ratings': 'შეფასება', 'save_rating': 'შეფასების შენახვა', 'rating_saved': 'შეფასება შენახულია.',
        'rating_invalid': 'აირჩიე შეფასება 1-დან 5-მდე.',
        'rating_login_required': 'პროდუქტის შესაფასებლად გაიარე ავტორიზაცია.', 'sign_in_to_rate': 'შეფასების დასატოვებლად გაიარე ავტორიზაცია.',
    },
    'ru': {
        'rate_product': 'Оцените товар', 'your_rating': 'Ваша оценка',
        'ratings': 'оценок', 'save_rating': 'Сохранить оценку', 'rating_saved': 'Оценка сохранена.',
        'rating_invalid': 'Выберите оценку от 1 до 5.',
        'rating_login_required': 'Войдите, чтобы оценить товар.', 'sign_in_to_rate': 'Войдите, чтобы оставить оценку.',
    },
}
for language, values in RATING_COPIES.items():
    COPIES[language].update(values)
