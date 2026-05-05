from __future__ import annotations

from PySide6.QtWidgets import QAbstractButton, QComboBox, QLabel, QLineEdit, QTableWidget, QWidget


SUPPORTED_LANGUAGES: tuple[tuple[str, str], ...] = (
    ("en", "English"),
    ("mr", "Marathi"),
    ("hi", "Hindi"),
)

SUPPORTED_LANGUAGE_CODES = {code for code, _label in SUPPORTED_LANGUAGES}
DEFAULT_LANGUAGE_CODE = "en"

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "mr": {
        "Action": "कृती",
        "Add Item": "आयटम जोडा",
        "Add New": "नवीन जोडा",
        "Add New Customer": "नवीन ग्राहक जोडा",
        "Add New Order": "नवीन ऑर्डर जोडा",
        "Address": "पत्ता",
        "All Due Dates": "सर्व देय तारखा",
        "All Workers": "सर्व कामगार",
        "Amount (INR)": "रक्कम (INR)",
        "Amount Received": "मिळालेली रक्कम",
        "Assign": "नेमून द्या",
        "Assign Worker": "कामगार नेमून द्या",
        "Assignee": "नेमलेला",
        "Balance": "शिल्लक",
        "Cancel": "रद्द करा",
        "Close": "बंद करा",
        "Create a new order for {name}": "{name} साठी नवीन ऑर्डर तयार करा",
        "Current Order": "सध्याची ऑर्डर",
        "Current assignee: Not assigned": "सध्याचा नेमलेला: नेमलेला नाही",
        "Customer Details": "ग्राहक तपशील",
        "Customer Name": "ग्राहक नाव",
        "Customer Search": "ग्राहक शोध",
        "Customer-item": "ग्राहक-आयटम",
        "Delivered": "डिलिव्हर झाले",
        "Due Date": "देय तारीख",
        "Enter address": "पत्ता प्रविष्ट करा",
        "Enter amount": "रक्कम प्रविष्ट करा",
        "Enter customer details, order metadata and items": "ग्राहक तपशील, ऑर्डर माहिती आणि आयटम प्रविष्ट करा",
        "Enter full name": "पूर्ण नाव प्रविष्ट करा",
        "Enter measurements": "मापे प्रविष्ट करा",
        "Item": "आयटम",
        "Item Status": "आयटम स्थिती",
        "Item-wise customer orders with NEW status rows shown first.": "NEW स्थितीच्या ओळी आधी दाखवून ग्राहकांच्या आयटमनिहाय ऑर्डर.",
        "Last Order": "शेवटची ऑर्डर",
        "Mark Payment": "पेमेंट नोंदवा",
        "Measurements": "मापे",
        "Name": "नाव",
        "New Order": "नवीन ऑर्डर",
        "Next": "पुढे",
        "No assigned work available for the selected worker.": "निवडलेल्या कामगारासाठी कोणतेही नेमलेले काम उपलब्ध नाही.",
        "No order items available for the selected filter.": "निवडलेल्या फिल्टरसाठी कोणतेही ऑर्डर आयटम उपलब्ध नाहीत.",
        "No store orders available yet.": "अजून कोणत्याही स्टोअर ऑर्डर उपलब्ध नाहीत.",
        "No customers found for this store. Use Add New to create the first customer.": "या स्टोअरसाठी कोणतेही ग्राहक सापडले नाहीत. पहिला ग्राहक तयार करण्यासाठी नवीन जोडा वापरा.",
        "No workers available.": "कामगार उपलब्ध नाहीत.",
        "Notes (Optional)": "टिपा (ऐच्छिक)",
        "Only customers created inside the active store are shown here. Use Add New to create a customer.": "येथे फक्त सक्रिय स्टोअरमध्ये तयार केलेले ग्राहक दिसतात. ग्राहक तयार करण्यासाठी नवीन जोडा वापरा.",
        "Ordered Items": "ऑर्डर केलेले आयटम",
        "Orders": "ऑर्डर",
        "Payment Method": "पेमेंट पद्धत",
        "Payment Summary": "पेमेंट सारांश",
        "Payments": "पेमेंट",
        "Phone": "फोन",
        "Previous": "मागे",
        "Print Receipt": "पावती छापा",
        "Priority": "प्राधान्य",
        "Qty": "संख्या",
        "Re-assign": "पुन्हा नेमून द्या",
        "Reassign": "पुन्हा नेमून द्या",
        "Reassign Worker": "कामगार पुन्हा नेमून द्या",
        "Remove Selected": "निवडलेले काढा",
        "Reset": "रीसेट",
        "Save Customer": "ग्राहक जतन करा",
        "Save Measurements": "मापे जतन करा",
        "Save Order": "ऑर्डर जतन करा",
        "Search": "शोधा",
        "Search by name, phone number or email": "नाव, फोन नंबर किंवा ईमेलने शोधा",
        "Select measurement": "माप निवडा",
        "Select worker": "कामगार निवडा",
        "TOTAL ASSIGNED": "एकूण नेमलेले",
        "TOTAL HOLD": "एकूण होल्ड",
        "TOTAL INSTITCHING": "एकूण शिवणकामात",
        "TOTAL READY": "एकूण तयार",
        "Total Items": "एकूण आयटम",
        "Update": "अपडेट",
        "Update Payment": "पेमेंट अपडेट करा",
        "WhatsApp": "व्हॉट्सअॅप",
        "Worker": "कामगार",
        "Worker Name": "कामगार नाव",
        "Workers": "कामगार",
    },
    "hi": {
        "Action": "कार्य",
        "Add Item": "आइटम जोड़ें",
        "Add New": "नया जोड़ें",
        "Add New Customer": "नया ग्राहक जोड़ें",
        "Add New Order": "नया ऑर्डर जोड़ें",
        "Address": "पता",
        "All Due Dates": "सभी देय तिथियां",
        "All Workers": "सभी कर्मचारी",
        "Amount (INR)": "राशि (INR)",
        "Amount Received": "प्राप्त राशि",
        "Assign": "असाइन करें",
        "Assign Worker": "कर्मचारी असाइन करें",
        "Assignee": "असाइनी",
        "Balance": "बकाया",
        "Cancel": "रद्द करें",
        "Close": "बंद करें",
        "Create a new order for {name}": "{name} के लिए नया ऑर्डर बनाएं",
        "Current Order": "वर्तमान ऑर्डर",
        "Current assignee: Not assigned": "वर्तमान असाइनी: असाइन नहीं",
        "Customer Details": "ग्राहक विवरण",
        "Customer Name": "ग्राहक नाम",
        "Customer Search": "ग्राहक खोज",
        "Customer-item": "ग्राहक-आइटम",
        "Delivered": "डिलीवर हुआ",
        "Due Date": "देय तिथि",
        "Enter address": "पता दर्ज करें",
        "Enter amount": "राशि दर्ज करें",
        "Enter customer details, order metadata and items": "ग्राहक विवरण, ऑर्डर जानकारी और आइटम दर्ज करें",
        "Enter full name": "पूरा नाम दर्ज करें",
        "Enter measurements": "माप दर्ज करें",
        "Item": "आइटम",
        "Item Status": "आइटम स्थिति",
        "Item-wise customer orders with NEW status rows shown first.": "NEW स्थिति वाली पंक्तियों को पहले दिखाते हुए ग्राहक ऑर्डर आइटमवार.",
        "Last Order": "अंतिम ऑर्डर",
        "Mark Payment": "भुगतान दर्ज करें",
        "Measurements": "माप",
        "Name": "नाम",
        "New Order": "नया ऑर्डर",
        "Next": "अगला",
        "No assigned work available for the selected worker.": "चुने गए कर्मचारी के लिए कोई असाइन किया गया काम उपलब्ध नहीं है.",
        "No order items available for the selected filter.": "चुने गए फिल्टर के लिए कोई ऑर्डर आइटम उपलब्ध नहीं है.",
        "No store orders available yet.": "अभी कोई स्टोर ऑर्डर उपलब्ध नहीं है.",
        "No customers found for this store. Use Add New to create the first customer.": "इस स्टोर के लिए कोई ग्राहक नहीं मिला. पहला ग्राहक बनाने के लिए नया जोड़ें इस्तेमाल करें.",
        "No workers available.": "कर्मचारी उपलब्ध नहीं हैं.",
        "Notes (Optional)": "नोट्स (वैकल्पिक)",
        "Only customers created inside the active store are shown here. Use Add New to create a customer.": "यहां केवल सक्रिय स्टोर में बनाए गए ग्राहक दिखते हैं. ग्राहक बनाने के लिए नया जोड़ें इस्तेमाल करें.",
        "Ordered Items": "ऑर्डर किए गए आइटम",
        "Orders": "ऑर्डर",
        "Payment Method": "भुगतान विधि",
        "Payment Summary": "भुगतान सारांश",
        "Payments": "भुगतान",
        "Phone": "फोन",
        "Previous": "पिछला",
        "Print Receipt": "रसीद प्रिंट करें",
        "Priority": "प्राथमिकता",
        "Qty": "संख्या",
        "Re-assign": "फिर असाइन करें",
        "Reassign": "फिर असाइन करें",
        "Reassign Worker": "कर्मचारी फिर असाइन करें",
        "Remove Selected": "चुना हुआ हटाएं",
        "Reset": "रीसेट",
        "Save Customer": "ग्राहक सेव करें",
        "Save Measurements": "माप सेव करें",
        "Save Order": "ऑर्डर सेव करें",
        "Search": "खोजें",
        "Search by name, phone number or email": "नाम, फोन नंबर या ईमेल से खोजें",
        "Select measurement": "माप चुनें",
        "Select worker": "कर्मचारी चुनें",
        "TOTAL ASSIGNED": "कुल असाइन",
        "TOTAL HOLD": "कुल होल्ड",
        "TOTAL INSTITCHING": "कुल सिलाई में",
        "TOTAL READY": "कुल तैयार",
        "Total Items": "कुल आइटम",
        "Update": "अपडेट",
        "Update Payment": "भुगतान अपडेट करें",
        "WhatsApp": "व्हाट्सऐप",
        "Worker": "कर्मचारी",
        "Worker Name": "कर्मचारी नाम",
        "Workers": "कर्मचारी",
    },
}


def normalize_language_code(language_code: str | None) -> str:
    normalized = (language_code or DEFAULT_LANGUAGE_CODE).strip().lower()
    return normalized if normalized in SUPPORTED_LANGUAGE_CODES else DEFAULT_LANGUAGE_CODE


def tr(text: str, language_code: str | None) -> str:
    normalized = normalize_language_code(language_code)
    if normalized == DEFAULT_LANGUAGE_CODE:
        return text
    return _TRANSLATIONS.get(normalized, {}).get(text, text)


def apply_widget_translations(root: QWidget, language_code: str | None) -> None:
    for widget in [root, *root.findChildren(QWidget)]:
        if isinstance(widget, QAbstractButton) or isinstance(widget, QLabel):
            _translate_text_property(widget, "text", language_code)
        if isinstance(widget, QLineEdit):
            _translate_text_property(widget, "placeholderText", language_code)


def translate_table_headers(
    table: QTableWidget,
    headers: tuple[str, ...],
    language_code: str | None,
) -> None:
    table.setHorizontalHeaderLabels([tr(header, language_code) for header in headers])


def set_combo_static_item_text(
    combo: QComboBox,
    index: int,
    text: str,
    language_code: str | None,
) -> None:
    if 0 <= index < combo.count():
        combo.setItemText(index, tr(text, language_code))


def _translate_text_property(widget: QWidget, property_name: str, language_code: str | None) -> None:
    getter = getattr(widget, property_name, None)
    setter = getattr(widget, f"set{property_name[:1].upper()}{property_name[1:]}", None)
    if getter is None or setter is None:
        return
    current_value = getter()
    if not isinstance(current_value, str) or not current_value:
        return
    property_key = f"_i18n_source_{property_name}"
    source_value = widget.property(property_key)
    if not isinstance(source_value, str):
        source_value = current_value
        widget.setProperty(property_key, source_value)
    setter(tr(source_value, language_code))
