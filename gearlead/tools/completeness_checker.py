from __future__ import annotations

from gearlead.schemas import InquiryData


CATEGORY_FIELDS = {
    "gaming_mouse": ["connection_type", "sensor_model", "polling_rate", "maximum_weight"],
    "mechanical_keyboard": ["layout", "connection_type", "hot_swappable", "language_layout"],
    "gaming_headset": ["connection_type", "platform_support", "microphone_type", "minimum_battery_life"],
    "custom_cable": ["cable_type", "connector_a", "connector_b", "aviator_connector"],
    "custom_keycap": ["material", "manufacturing_method", "profile", "layout"],
}

LABELS = {
    "company_name": "Customer company name", "country": "Customer country",
    "customer_type": "Customer type", "quantity": "Requested quantity",
    "target_market": "Target market", "required_delivery_date": "Required delivery date",
    "connection_type": "Connection type", "sensor_model": "Sensor model",
    "polling_rate": "Polling rate", "maximum_weight": "Maximum mouse weight",
    "layout": "Keyboard/keycap layout", "hot_swappable": "Hot-swap requirement",
    "language_layout": "Language layout", "platform_support": "Platform compatibility",
    "microphone_type": "Microphone type", "minimum_battery_life": "Minimum battery life",
    "cable_type": "Cable form", "connector_a": "Connector A", "connector_b": "Connector B",
    "aviator_connector": "Aviator connector", "material": "Keycap material",
    "manufacturing_method": "Manufacturing method", "profile": "Keycap profile",
}


def check_missing_fields(inquiry: InquiryData) -> tuple[list[str], int]:
    required: list[tuple[str, object]] = [
        ("company_name", inquiry.customer.company_name),
        ("country", inquiry.customer.country),
        ("customer_type", inquiry.customer.customer_type if inquiry.customer.customer_type != "unknown" else ""),
        ("quantity", inquiry.purchase_request.quantity),
        ("target_market", inquiry.purchase_request.target_market),
        ("required_delivery_date", inquiry.purchase_request.required_delivery_date),
    ]
    for field in CATEGORY_FIELDS.get(inquiry.purchase_request.category, []):
        value = inquiry.product_requirements.get(field)
        required.append((field, value if value is not False else False))
    missing = [LABELS.get(field, field.replace("_", " ").title()) for field, value in required if value in (None, "", False)]
    completed = len(required) - len(missing)
    score = round((completed / len(required)) * 100) if required else 0
    return missing, score

