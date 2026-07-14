from django import template
from django.utils.translation import get_language

register = template.Library()


@register.filter
def get_item(mapping, key):
    if not isinstance(mapping, dict):
        return None
    return mapping.get(key)


STATUS_LABELS = {
    "en": {
        "pending": "Pending", "confirmed": "Confirmed", "processing": "Processing", "shipped": "Shipped",
        "delivered": "Delivered", "cancelled": "Cancelled", "refunded": "Refunded", "approved": "Approved",
        "rejected": "Rejected", "completed": "Completed", "in_review": "In review", "resolved": "Resolved",
    },
    "ka": {
        "pending": "მოლოდინში", "confirmed": "დადასტურებული", "processing": "მუშავდება", "shipped": "გაგზავნილი",
        "delivered": "მიწოდებული", "cancelled": "გაუქმებული", "refunded": "თანხა დაბრუნებულია", "approved": "დამტკიცებული",
        "rejected": "უარყოფილი", "completed": "დასრულებული", "in_review": "განხილვაში", "resolved": "გადაწყვეტილი",
    },
    "ru": {
        "pending": "Ожидает", "confirmed": "Подтверждён", "processing": "Обрабатывается", "shipped": "Отправлен",
        "delivered": "Доставлен", "cancelled": "Отменён", "refunded": "Возврат средств", "approved": "Одобрен",
        "rejected": "Отклонён", "completed": "Завершён", "in_review": "На рассмотрении", "resolved": "Решён",
    },
}


@register.filter
def localized_status(value):
    language = (get_language() or "en").split("-")[0]
    labels = STATUS_LABELS.get(language, STATUS_LABELS["en"])
    return labels.get(str(value), str(value).replace("_", " ").title())