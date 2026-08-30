import json
import re
from datetime import datetime, timedelta
from dateutil import parser as date_parser

EXCEL_EPOCH = datetime(1899, 12, 30)

MISSING_SENTINELS = {
    "deals": {"8", 8, 8.0},
    "work_orders": {"29", 29, 29.0},
}

STAGE_ALIASES = {
    "won": "Won",
    "closed won": "Won",
    "project won": "Won",
    "dead": "Lost",
    "lost": "Lost",
    "project lost": "Lost",
    "on hold": "On Hold",
    "open": "Open",
}

PROBABILITY_MAP = {
    "low": 0.25,
    "medium": 0.50,
    "high": 0.75,
}

def clean_text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value if value else None

def normalize_missing(value, dataset: str):
    if value is None:
        return None
    sentinels = MISSING_SENTINELS[dataset]
    if value in sentinels or str(value).strip() in {str(x) for x in sentinels}:
        return None
    return value

def parse_number(value, dataset: str):
    value = normalize_missing(value, dataset)
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[₹,\s]", "", str(value))
    try:
        return float(text)
    except ValueError:
        return None

def parse_date(value, dataset: str):
    value = normalize_missing(value, dataset)
    if value is None:
        return None

    if isinstance(value, (int, float)):
        # Excel serial dates in the supplied source sheets are around 45,000+
        if value > 1000:
            return (EXCEL_EPOCH + timedelta(days=float(value))).date().isoformat()
        return None

    text = str(value).strip()
    if not text:
        return None

    # Some monday imports expose Excel serial dates as numeric strings.
    try:
        numeric = float(text)
        if numeric > 1000:
            return (EXCEL_EPOCH + timedelta(days=numeric)).date().isoformat()
    except ValueError:
        pass

    # monday date text is usually already human-readable / ISO-like
    try:
        return date_parser.parse(text, fuzzy=False).date().isoformat()
    except Exception:
        return None

def column_title_map(schema: dict) -> dict:
    return {c["id"]: c["title"] for c in schema.get("columns", [])}

def flatten_monday_items(schema: dict, items: list[dict]) -> list[dict]:
    title_by_id = column_title_map(schema)
    rows = []
    for item in items:
        row = {"_item_id": item["id"], "_item_name": item["name"]}
        for col in item.get("column_values", []):
            title = title_by_id.get(col["id"], col["id"])
            row[title] = col.get("text")
            row[f"__raw__{title}"] = col.get("value")
        rows.append(row)
    return rows

def normalize_deals(rows: list[dict]) -> tuple[list[dict], list[str]]:
    clean = []
    warnings = []

    for row in rows:
        # Drop malformed repeated-header-like source rows.
        if clean_text(row.get("Deal Status")) == "Deal Status":
            warnings.append(f"Dropped malformed header-like deal row: {row.get('_item_name')}")
            continue

        probability_raw = normalize_missing(row.get("Closure Probability"), "deals")
        probability = None
        if probability_raw is not None:
            probability = PROBABILITY_MAP.get(str(probability_raw).lower())
            if probability is None:
                n = parse_number(probability_raw, "deals")
                if n is not None:
                    probability = n / 100 if n > 1 else n

        status = normalize_missing(row.get("Deal Status"), "deals")
        status_norm = STAGE_ALIASES.get(str(status).lower(), status) if status else None

        clean.append({
            "item_id": row.get("_item_id"),
            "deal_name": clean_text(row.get("Deal Name")) or clean_text(row.get("_item_name")),
            "owner": normalize_missing(row.get("Owner code"), "deals"),
            "client": clean_text(row.get("Client Code")),
            "status": status_norm,
            "close_date": parse_date(row.get("Close Date (A)"), "deals"),
            "probability": probability,
            "deal_value": parse_number(row.get("Masked Deal value"), "deals"),
            "tentative_close_date": parse_date(row.get("Tentative Close Date"), "deals"),
            "stage": clean_text(row.get("Deal Stage")),
            "product": normalize_missing(row.get("Product deal"), "deals"),
            "sector": normalize_missing(row.get("Sector/service"), "deals"),
            "created_date": parse_date(row.get("Created Date"), "deals"),
        })

    return clean, warnings

def normalize_work_orders(rows: list[dict]) -> tuple[list[dict], list[str]]:
    clean = []
    warnings = []

    for row in rows:
        clean.append({
            "item_id": row.get("_item_id"),
            "deal_name": clean_text(row.get("Deal name masked")) or clean_text(row.get("_item_name")),
            "customer": clean_text(row.get("Customer Name Code")),
            "serial": clean_text(row.get("Serial #")),
            "nature_of_work": normalize_missing(row.get("Nature of Work"), "work_orders"),
            "execution_status": normalize_missing(row.get("Execution Status"), "work_orders"),
            "data_delivery_date": parse_date(row.get("Data Delivery Date"), "work_orders"),
            "po_date": parse_date(row.get("Date of PO/LOI"), "work_orders"),
            "document_type": normalize_missing(row.get("Document Type"), "work_orders"),
            "probable_start_date": parse_date(row.get("Probable Start Date"), "work_orders"),
            "probable_end_date": parse_date(row.get("Probable End Date"), "work_orders"),
            "owner": normalize_missing(row.get("BD/KAM Personnel code"), "work_orders"),
            "sector": normalize_missing(row.get("Sector"), "work_orders"),
            "type_of_work": clean_text(row.get("Type of Work")),
            "platform": normalize_missing(
                row.get("Is any Skylark software platform part of the client deliverables in this deal?"),
                "work_orders"
            ),
            "amount_ex_gst": parse_number(row.get("Amount in Rupees (Excl of GST) (Masked)"), "work_orders"),
            "amount_inc_gst": parse_number(row.get("Amount in Rupees (Incl of GST) (Masked)"), "work_orders"),
            "billed_ex_gst": parse_number(row.get("Billed Value in Rupees (Excl of GST.) (Masked)"), "work_orders"),
            "billed_inc_gst": parse_number(row.get("Billed Value in Rupees (Incl of GST.) (Masked)"), "work_orders"),
            "collected_inc_gst": parse_number(row.get("Collected Amount in Rupees (Incl of GST.) (Masked)"), "work_orders"),
            "to_bill_ex_gst": parse_number(row.get("Amount to be billed in Rs. (Exl. of GST) (Masked)"), "work_orders"),
            "receivable": parse_number(row.get("Amount Receivable (Masked)"), "work_orders"),
            "invoice_status": normalize_missing(row.get("Invoice Status"), "work_orders"),
            "wo_status": normalize_missing(row.get("WO Status (billed)"), "work_orders"),
            "billing_status": normalize_missing(row.get("Billing Status"), "work_orders"),
        })

    return clean, warnings
