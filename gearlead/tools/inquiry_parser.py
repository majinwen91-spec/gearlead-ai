from __future__ import annotations

import json
import re
from pathlib import Path

from gearlead.llm_client import LLMClient, LLMError
from gearlead.schemas import InquiryData, model_validate_compat


COUNTRIES = {
    "germany": "Germany", "german": "Germany", "united states": "United States",
    "usa": "United States", "u.s.": "United States", "america": "United States",
    "united kingdom": "United Kingdom", "uk": "United Kingdom", "britain": "United Kingdom",
    "france": "France", "french": "France", "japan": "Japan", "japanese": "Japan",
    "poland": "Poland", "polish": "Poland", "canada": "Canada", "australia": "Australia",
    "netherlands": "Netherlands", "spain": "Spain", "italy": "Italy", "brazil": "Brazil",
    "mexico": "Mexico", "hong kong": "Hong Kong", "singapore": "Singapore",
}

COUNTRY_PATTERN = "|".join(sorted((re.escape(key) for key in COUNTRIES), key=len, reverse=True))

CORPORATE_SUFFIXES = r"(?:GmbH|Ltd\.?|LLC|Inc\.?|Co\.?|S\.A\.?|Sp\. z o\.o\.|B\.V\.)"


def _contains(text: str, *terms: str) -> bool:
    return any(term.lower() in text.lower() for term in terms)


def _first_match(pattern: str, text: str, flags: int = re.IGNORECASE) -> str:
    match = re.search(pattern, text, flags)
    if not match:
        return ""
    return next((group.strip() for group in match.groups() if group is not None), "")


def _normalize_country(value: str) -> str:
    return COUNTRIES.get(value.strip().lower(), "")


def _first_country(text: str) -> str:
    match = re.search(rf"\b({COUNTRY_PATTERN})\b", text, re.IGNORECASE)
    return _normalize_country(match.group(1)) if match else ""


def _customer_country(text: str) -> str:
    patterns = [
        rf"(?:based|located|headquartered)\s+in\s+(?:the\s+)?({COUNTRY_PATTERN})\b",
        rf"(?:company|brand|distributor|retailer|buyer)\s+in\s+(?:the\s+)?({COUNTRY_PATTERN})\b",
        rf"(?:we are|we're)\s+(?:from\s+)?(?:a|an)?\s*({COUNTRY_PATTERN})\b",
    ]
    for pattern in patterns:
        value = _first_match(pattern, text)
        if value:
            return _normalize_country(value)
    return _first_country(text)


def _target_market(text: str) -> str:
    patterns = [
        rf"(?:target|sales|distribution)\s+market\s+(?:is\s+|in\s+|for\s+)?(?:the\s+)?({COUNTRY_PATTERN})\b",
        rf"(?:sold|selling|distributed)\s+in\s+(?:the\s+)?({COUNTRY_PATTERN})\b",
        rf"for\s+(?:our\s+|the\s+)?({COUNTRY_PATTERN})\s+(?:market|stores|customers|retail)\b",
        rf"for\s+(?:our\s+|the\s+)?({COUNTRY_PATTERN})\b",
    ]
    for pattern in patterns:
        value = _first_match(pattern, text)
        if value:
            return _normalize_country(value)
    return ""


def _delivery_destination(text: str) -> str:
    value = _first_match(
        r"(?:deliver(?:y)?|ship(?:ping)?)\s+to\s+([^,.;]+?)(?=\s+(?:by|before|on)\s+|[,.;]|$)",
        text,
    )
    return value.strip() if value else ""


def _extract_company(text: str) -> str:
    patterns = [
        rf"(?:from|represent(?:ing)?|company is|we are)\s+([A-Z][\w&' -]{{1,50}}?\s+{CORPORATE_SUFFIXES})(?=\s|,)",
        rf"([A-Z][\w&' -]{{1,50}}?\s+{CORPORATE_SUFFIXES})(?=\s|,)",
    ]
    for pattern in patterns:
        company = _first_match(pattern, text)
        if company:
            return re.sub(r"^(?:from|representing)\s+", "", company, flags=re.IGNORECASE)
    return ""


def _extract_quantity(text: str) -> int | None:
    patterns = [
        r"(?:initial|first|trial|order|quantity|qty|need|want|plan|quote)\D{0,12}([\d,]+)(?!%)\s+(?:[A-Za-z-]+\s+){0,4}(?:units|pcs|pieces|sets|cables|keyboards|mice|headsets)\b",
        r"(?:initial|first|trial|order|quantity|qty|need|looking for|would like)\D{0,24}([\d,]+)\s*(?:units|pcs|pieces|sets|cables|keyboards|mice|headsets)",
    ]
    for pattern in patterns:
        value = _first_match(pattern, text)
        if value:
            return int(value.replace(",", ""))
    for match in re.finditer(r"([\d,]+)\s*(?:units|pcs|pieces|sets|cables)\b", text, re.IGNORECASE):
        prefix = text[max(0, match.start() - 24):match.start()].lower()
        if "annual" not in prefix and "per year" not in prefix and "yearly" not in prefix:
            return int(match.group(1).replace(",", ""))
    return None


def _extract_annual_quantity(text: str) -> int | None:
    value = _first_match(r"(?:annual(?:ly)?|per year|yearly)\D{0,20}([\d,]+)|([\d,]+)\s*(?:units|pcs|sets)?\s*(?:per year|annually)", text)
    if not value:
        match = re.search(r"([\d,]+)\s*(?:units|pcs|sets)?\s*(?:per year|annually)", text, re.IGNORECASE)
        value = match.group(1) if match else ""
    return int(value.replace(",", "")) if value else None


def _category(text: str) -> str:
    lower = text.lower()
    if _contains(lower, "keyboard") and not _contains(lower, "keyboard cable"):
        return "mechanical_keyboard"
    if _contains(lower, "keycap set", "key cap set", "keycap kit", "key cap kit") or (
        _contains(lower, "keycap", "key cap") and not _contains(lower, "keyboard")
    ):
        return "custom_keycap"
    if _contains(lower, "keyboard cable", "coiled cable", "aviator cable", "yc8", "gx16", "lemo"):
        return "custom_cable"
    if _contains(lower, "headset", "headphone"):
        return "gaming_headset"
    if _contains(lower, "gaming mouse", "mice", "mouse"):
        return "gaming_mouse"
    return "unknown"


def _connection(text: str) -> str:
    if _contains(text, "tri-mode", "trimode", "three-mode"):
        return "Tri-mode"
    values = []
    if _contains(text, "2.4g", "2.4 ghz"):
        values.append("2.4G")
    if _contains(text, "bluetooth"):
        values.append("Bluetooth")
    if _contains(text, "wireless") and not values:
        values.append("Wireless")
    if _contains(text, "usb headset", "usb connection"):
        values.append("USB")
    if _contains(text, "3.5mm"):
        values.append("3.5mm")
    if _contains(text, "wired") and not values:
        values.append("Wired")
    return ",".join(values)


def _extract_specs(text: str, category: str) -> dict[str, object]:
    specs: dict[str, object] = {}
    connection = _connection(text)
    if connection:
        specs["connection_type"] = connection
    if category == "gaming_mouse":
        sensor = _first_match(r"(PAW\d{4})", text)
        polling = _first_match(r"\b(1K|4K|8K)\s*(?:Hz|polling)?", text)
        weight = _first_match(r"(?:under|below|maximum|max\.?|less than)\s*(\d{2,3})\s*g|\b(\d{2,3})\s*g\s*(?:weight|mouse)", text)
        if not weight:
            match = re.search(r"(?:under|below|maximum|max\.?|less than)\s*(\d{2,3})\s*g", text, re.IGNORECASE)
            weight = match.group(1) if match else ""
        dpi = _first_match(r"([\d,]{4,6})\s*DPI", text)
        if sensor: specs["sensor_model"] = sensor.upper()
        if polling: specs["polling_rate"] = polling.upper()
        if weight: specs["maximum_weight"] = int(weight)
        if dpi: specs["max_dpi"] = int(dpi.replace(",", ""))
        if _contains(text, "ergonomic"): specs["shape"] = "Ergonomic"
        if _contains(text, "symmetrical", "ambidextrous"): specs["shape"] = "Symmetrical"
        if _contains(text, "optical switch"): specs["switch_type"] = "Optical"
    elif category == "mechanical_keyboard":
        layout = _first_match(r"\b(60%|65%|75%|TKL|full[- ]?size)(?=\s|[,.;])", text)
        if layout: specs["layout"] = layout.replace("full size", "Full-size").replace("full-size", "Full-size")
        if _contains(text, "gasket"): specs["mounting_structure"] = "Gasket"
        if _contains(text, "not hot-swappable", "not hot swappable", "non-hot-swappable", "without hot-swap"):
            specs["hot_swappable"] = False
        elif _contains(text, "hot-swappable", "hot swappable", "hotswap"):
            specs["hot_swappable"] = True
        if _contains(text, "pbt"): specs["keycap_material"] = "PBT"
        if _contains(text, "abs keycap"): specs["keycap_material"] = "ABS"
        profile = _first_match(r"\b(Cherry|OEM|XDA|MDA|SA)\s+profile", text)
        if profile: specs["keycap_profile"] = profile
        language = _first_match(r"\b(ANSI-US|ISO-UK|ISO-DE|ISO-FR)\b", text)
        if language: specs["language_layout"] = language.upper()
        if _contains(text, "aluminum", "aluminium"): specs["case_material"] = "Aluminum"
        if _contains(text, "via"): specs["firmware_support"] = "VIA"
        if _contains(text, "qmk"): specs["firmware_support"] = "QMK"
    elif category == "gaming_headset":
        driver = _first_match(r"\b(40|50)\s*mm\s*(?:driver)?", text)
        battery = _first_match(r"(?:at least|minimum|over)?\s*(\d{2,3})\s*(?:hours|hrs|h)\b", text)
        if driver: specs["driver_size"] = f"{driver}mm"
        if battery: specs["minimum_battery_life"] = int(battery)
        if _contains(text, "7.1"): specs["audio_channel"] = "Virtual 7.1"
        if _contains(text, "detachable mic", "detachable microphone"): specs["microphone_type"] = "Detachable"
        if _contains(text, "retractable mic", "retractable microphone"): specs["microphone_type"] = "Retractable"
        if _contains(text, "enc"): specs["noise_reduction"] = "ENC"
        platforms = [value for value in ["PC", "PS5", "Xbox", "Switch"] if value.lower() in text.lower()]
        if platforms: specs["platform_support"] = ",".join(platforms)
    elif category == "custom_cable":
        if _contains(text, "coiled"): specs["cable_type"] = "Coiled"
        elif _contains(text, "straight"): specs["cable_type"] = "Straight"
        connector = _first_match(r"(USB-[AC])\s+(?:to|-)\s+(USB-C|USB-A|Mini USB|Micro USB)", text)
        if connector:
            match = re.search(r"(USB-[AC])\s+(?:to|-)\s+(USB-C|USB-A|Mini USB|Micro USB)", text, re.IGNORECASE)
            specs["connector_a"], specs["connector_b"] = match.group(1).upper(), match.group(2)
        for value in ["YC8", "GX16", "LEMO-style"]:
            if value.lower().replace("-style", "") in text.lower(): specs["aviator_connector"] = value
        length = _first_match(r"(\d+(?:\.\d+)?)\s*m\b", text)
        coil = _first_match(r"(\d+)\s*cm\s*coil", text)
        if length: specs["total_length"] = f"{length}m"
        if coil: specs["coil_length"] = f"{coil}cm"
        if _contains(text, "paracord"): specs["sleeve_material"] = "Paracord"
        if _contains(text, "pet sleeve", "pet braided"): specs["sleeve_material"] = "PET"
        if _contains(text, "usb 3.0"): specs["data_standard"] = "USB 3.0"
    elif category == "custom_keycap":
        if _contains(text, "pbt"): specs["material"] = "PBT"
        if _contains(text, "abs"): specs["material"] = "ABS"
        if _contains(text, "five-sided dye", "five sided dye"): specs["manufacturing_method"] = "Five-sided Dye-sublimation"
        elif _contains(text, "dye-sub", "dye sublimation"): specs["manufacturing_method"] = "Dye-sublimation"
        elif _contains(text, "double-shot", "double shot"): specs["manufacturing_method"] = "Double-shot"
        profile = _first_match(r"\b(Cherry|OEM|XDA|SA)\s+profile", text)
        if profile: specs["profile"] = profile
        language = _first_match(r"\b(ISO-UK|ISO-DE|ISO-FR|ANSI-US)\b", text)
        if language:
            specs["language"] = {"ISO-UK": "UK", "ISO-DE": "German", "ISO-FR": "French", "ANSI-US": "US"}[language.upper()]
            specs["layout"] = "ISO" if language.upper().startswith("ISO") else "ANSI"
        count = _first_match(r"(\d{3})[- ]?(?:key|piece|pc)\s*(?:set|kit)", text)
        if count: specs["key_count"] = int(count)
        if _contains(text, "shine-through", "shine through"): specs["shine_through"] = True
    return specs


def rule_based_extract(text: str) -> InquiryData:
    clean = " ".join(text.split())
    lower = clean.lower()
    category = _category(clean)
    email_match = re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", clean)
    website_match = re.search(r"(?:https?://|www\.)[\w.-]+\.[A-Za-z]{2,}(?:/\S*)?", clean)
    email = email_match.group(0) if email_match else ""
    website = website_match.group(0).rstrip(".,;") if website_match else ""
    country = _customer_country(clean)
    explicit_target_market = _target_market(clean)
    target_market = explicit_target_market or country
    delivery_destination = _delivery_destination(clean)
    customer_type = next((value for value in ["distributor", "brand", "retailer", "ecommerce", "trading", "wholesaler"] if value in lower), "unknown")
    certifications = [value for value in ["CE", "FCC", "RoHS", "UKCA"] if re.search(rf"\b{value}\b", clean, re.IGNORECASE)]
    target_price_match = re.search(r"(?:target price|below|under)\s*(?:USD|US\$|\$)?\s*(\d+(?:\.\d+)?)", clean, re.IGNORECASE)
    target_price = float(target_price_match.group(1)) if target_price_match else None
    delivery = _first_match(
        r"(?:deliver(?:y|ed)?|arrive|needed|launch(?: date)?)\s+(?:is\s+|by\s+|before\s+)?([^.,;]+)|(?:for\s+(?:an?\s+)?)?([^.,;]+?)\s+launch\b",
        clean,
    )
    quality_warnings = []
    commercial_warnings = []
    risk_signals = []
    if _contains(lower, "western union", "crypto payment", "personal account"):
        risk_signals.append("Unusual payment method requested.")
    if _contains(lower, "passport", "bank login", "sensitive document"):
        risk_signals.append("Sensitive information requested before qualification.")
    if _contains(lower, "without contract", "bypass contract", "outside the platform"):
        risk_signals.append("Buyer asks to bypass the formal contracting process.")
    if _contains(lower, "exclusive", "exclusivity") and not _contains(lower, "channel", "stores", "distribution network"):
        commercial_warnings.append("Exclusivity requested without channel information.")
    if _contains(lower, "cheapest", "lowest price", "best price") and not _extract_company(clean) and len(_extract_specs(clean, category)) <= 1:
        quality_warnings.append("Price-only inquiry provides minimal buyer and product context.")
    if len(clean) < 35:
        quality_warnings.append("Inquiry content is unusually short.")
    if target_market and not explicit_target_market:
        commercial_warnings.append("Target market is inferred from the customer country and should be confirmed.")
    quantity = _extract_quantity(clean)
    customization = {
        "logo": _contains(lower, "custom logo", "private label", "our logo"),
        "color": _contains(lower, "custom color", "pantone", "colour combination", "color combination"),
        "packaging": _contains(lower, "custom packaging", "private label packaging", "retail packaging", "retail box", "branded packaging"),
        "firmware": _contains(lower, "custom firmware", "firmware modification"),
        "language_layout": bool(re.search(r"\bISO-(?:DE|UK|FR)\b", clean, re.IGNORECASE)),
        "new_mold": _contains(lower, "new mold", "new mould", "custom shell", "new tooling"),
        "artwork": _contains(lower, "custom artwork", "design files", "original artwork"),
    }
    data = {
        "customer": {
            "company_name": _extract_company(clean), "country": country,
            "customer_type": customer_type, "email": email, "website": website,
        },
        "purchase_request": {
            "category": category, "quantity": quantity,
            "annual_quantity": _extract_annual_quantity(clean), "target_price": target_price,
            "currency": "USD" if target_price is not None or _contains(lower, "usd", "$") else "",
            "target_market": target_market, "delivery_destination": delivery_destination,
            "required_delivery_date": delivery, "sample_required": _contains(lower, "sample", "prototype"),
        },
        "product_requirements": _extract_specs(clean, category),
        "customization": customization,
        "commercial_requirements": {
            "quotation_requested": _contains(lower, "quotation", "quote", "best price", "pricing"),
            "catalog_requested": _contains(lower, "catalog", "catalogue"),
            "certification_requested": certifications,
            "payment_terms_requested": _contains(lower, "payment terms", "net 30", "net 60"),
            "exclusivity_requested": _contains(lower, "exclusive", "exclusivity"),
        },
        "quality_warnings": quality_warnings,
        "commercial_warnings": commercial_warnings,
        "risk_signals": risk_signals,
    }
    return model_validate_compat(InquiryData, data)


def extract_inquiry_fields(text: str, use_llm: bool = False, client: LLMClient | None = None) -> InquiryData:
    if not text or len(text.strip()) < 8:
        raise ValueError("Inquiry text is empty or too short to analyze.")
    if use_llm:
        llm = client or LLMClient.from_settings()
        system = (Path(__file__).resolve().parents[1] / "prompts" / "inquiry_extraction.md").read_text(encoding="utf-8")
        try:
            payload = json.loads(llm.chat(system, text, json_mode=True))
            return model_validate_compat(InquiryData, payload)
        except (LLMError, json.JSONDecodeError, ValueError):
            pass
    return rule_based_extract(text)
