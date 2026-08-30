from datetime import date
from collections import Counter

OPEN_STATUSES = {"Open", "On Hold"}


def _clean_text(value):
    """
    Normalizes text-like values coming from monday.com.

    The original Work Orders dataset uses 29 as a missing-value sentinel.
    The Deals dataset uses 8 as a missing-value sentinel.
    """
    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    if text in {"8", "29"}:
        return None

    return text


def _in_period(iso_date, start_date=None, end_date=None):
    if not iso_date:
        return False

    try:
        d = date.fromisoformat(str(iso_date))
    except Exception:
        return False

    if start_date and d < start_date:
        return False

    if end_date and d > end_date:
        return False

    return True


def filter_sector(rows, sector):
    if not sector:
        return rows

    target = sector.strip().lower()

    return [
        r
        for r in rows
        if (_clean_text(r.get("sector")) or "").lower() == target
    ]


def pipeline_summary(
    deals,
    sector=None,
    start_date=None,
    end_date=None
):
    rows = filter_sector(deals, sector)

    if start_date or end_date:
        rows = [
            r
            for r in rows
            if _in_period(
                r.get("tentative_close_date")
                or r.get("close_date"),
                start_date,
                end_date
            )
        ]

    active = [
        r
        for r in rows
        if _clean_text(r.get("status")) in OPEN_STATUSES
    ]

    known_value = [
        r
        for r in active
        if r.get("deal_value") is not None
    ]

    weighted_values = [
        r["deal_value"] * r["probability"]
        for r in active
        if r.get("deal_value") is not None
        and r.get("probability") is not None
    ]

    by_stage = {}

    for r in active:
        stage = _clean_text(r.get("stage")) or "Missing"

        by_stage.setdefault(
            stage,
            {
                "count": 0,
                "value": 0.0
            }
        )

        by_stage[stage]["count"] += 1

        if r.get("deal_value") is not None:
            by_stage[stage]["value"] += r["deal_value"]

    return {
        "active_deals": len(active),

        "known_value_deals": len(known_value),

        "pipeline_value": sum(
            r["deal_value"]
            for r in known_value
        ),

        "weighted_pipeline": sum(
            weighted_values
        ),

        "missing_value_count": sum(
            r.get("deal_value") is None
            for r in active
        ),

        "missing_probability_count": sum(
            r.get("probability") is None
            for r in active
        ),

        "by_stage": by_stage,
    }


def revenue_summary(
    work_orders,
    sector=None
):
    rows = filter_sector(work_orders, sector)

    return {
        "work_orders": len(rows),

        "contract_value_ex_gst": sum(
            r.get("amount_ex_gst") or 0
            for r in rows
        ),

        "billed_ex_gst": sum(
            r.get("billed_ex_gst") or 0
            for r in rows
        ),

        "collected_inc_gst": sum(
            r.get("collected_inc_gst") or 0
            for r in rows
        ),

        "receivable": sum(
            r.get("receivable") or 0
            for r in rows
        ),

        "to_bill_ex_gst": sum(
            r.get("to_bill_ex_gst") or 0
            for r in rows
        ),

        "missing_billed_ex_gst": sum(
            r.get("billed_ex_gst") is None
            for r in rows
        ),

        "missing_collected": sum(
            r.get("collected_inc_gst") is None
            for r in rows
        ),

        "missing_receivable": sum(
            r.get("receivable") is None
            for r in rows
        ),
    }


def operations_summary(
    work_orders,
    sector=None
):
    rows = filter_sector(work_orders, sector)

    execution_statuses = []

    wo_statuses = []

    invoice_statuses = []

    for r in rows:
        execution = _clean_text(
            r.get("execution_status")
        )

        wo_status = _clean_text(
            r.get("wo_status")
        )

        invoice_status = _clean_text(
            r.get("invoice_status")
        )

        execution_statuses.append(
            execution or "Missing"
        )

        wo_statuses.append(
            wo_status or "Missing"
        )

        invoice_statuses.append(
            invoice_status or "Missing"
        )

    execution_counts = Counter(
        execution_statuses
    )

    wo_counts = Counter(
        wo_statuses
    )

    invoice_counts = Counter(
        invoice_statuses
    )

    open_work_orders = sum(
        status.lower() == "open"
        for status in wo_statuses
        if status != "Missing"
    )

    closed_work_orders = sum(
        status.lower() == "closed"
        for status in wo_statuses
        if status != "Missing"
    )

    missing_execution = execution_counts.get(
        "Missing",
        0
    )

    missing_wo_status = wo_counts.get(
        "Missing",
        0
    )

    return {
        "work_orders": len(rows),

        "open_work_orders": open_work_orders,

        "closed_work_orders": closed_work_orders,

        "missing_wo_status": missing_wo_status,

        "missing_execution_status": missing_execution,

        "execution_status_counts": dict(
            execution_counts
        ),

        "wo_status_counts": dict(
            wo_counts
        ),

        "invoice_status_counts": dict(
            invoice_counts
        ),
    }


def collection_summary(
    work_orders,
    sector=None
):
    rows = filter_sector(work_orders, sector)

    receivable_rows = [
        r
        for r in rows
        if (r.get("receivable") or 0) > 0
    ]

    return {
        "work_orders": len(rows),

        "collected_inc_gst": sum(
            r.get("collected_inc_gst") or 0
            for r in rows
        ),

        "receivable": sum(
            r.get("receivable") or 0
            for r in rows
        ),

        "accounts_with_receivable": len(
            receivable_rows
        ),

        "missing_collection_amount": sum(
            r.get("collected_inc_gst") is None
            for r in rows
        ),

        "missing_receivable": sum(
            r.get("receivable") is None
            for r in rows
        ),
    }


def sector_performance(
    deals,
    work_orders
):
    """
    Cross-board sector-level BI.

    This intentionally aggregates by sector rather than attempting
    an unreliable row-level join between Deals and Work Orders.
    """

    sectors = set()

    for row in deals:
        sector = _clean_text(
            row.get("sector")
        )

        if sector:
            sectors.add(sector)

    for row in work_orders:
        sector = _clean_text(
            row.get("sector")
        )

        if sector:
            sectors.add(sector)

    results = {}

    for sector in sorted(sectors):
        pipeline = pipeline_summary(
            deals,
            sector=sector
        )

        revenue = revenue_summary(
            work_orders,
            sector=sector
        )

        operations = operations_summary(
            work_orders,
            sector=sector
        )

        collections = collection_summary(
            work_orders,
            sector=sector
        )

        results[sector] = {
            "pipeline": pipeline,
            "revenue": revenue,
            "operations": operations,
            "collections": collections,
        }

    return results


def strongest_pipeline_sector(
    deals
):
    sector_data = {}

    sectors = {
        _clean_text(r.get("sector"))
        for r in deals
        if _clean_text(r.get("sector"))
    }

    for sector in sectors:
        summary = pipeline_summary(
            deals,
            sector=sector
        )

        sector_data[sector] = summary

    if not sector_data:
        return None

    best_sector = max(
        sector_data.items(),
        key=lambda item: item[1]["pipeline_value"]
    )

    sector_name, metrics = best_sector

    return {
        "sector": sector_name,
        **metrics
    }


def highest_revenue_sector(
    work_orders
):
    sector_data = {}

    sectors = {
        _clean_text(r.get("sector"))
        for r in work_orders
        if _clean_text(r.get("sector"))
    }

    for sector in sectors:
        summary = revenue_summary(
            work_orders,
            sector=sector
        )

        sector_data[sector] = summary

    if not sector_data:
        return None

    best_sector = max(
        sector_data.items(),
        key=lambda item: item[1]["contract_value_ex_gst"]
    )

    sector_name, metrics = best_sector

    return {
        "sector": sector_name,
        **metrics
    }


def highest_receivable_sector(
    work_orders
):
    sector_data = {}

    sectors = {
        _clean_text(r.get("sector"))
        for r in work_orders
        if _clean_text(r.get("sector"))
    }

    for sector in sectors:
        summary = collection_summary(
            work_orders,
            sector=sector
        )

        sector_data[sector] = summary

    if not sector_data:
        return None

    best_sector = max(
        sector_data.items(),
        key=lambda item: item[1]["receivable"]
    )

    sector_name, metrics = best_sector

    return {
        "sector": sector_name,
        **metrics
    }


def operational_bottlenecks(
    work_orders,
    sector=None
):
    rows = filter_sector(
        work_orders,
        sector
    )

    operations = operations_summary(
        rows
    )

    not_started = 0
    ongoing = 0
    paused = 0
    partial = 0
    pending_client = 0

    for r in rows:
        status = (
            _clean_text(
                r.get("execution_status")
            )
            or ""
        ).lower()

        if status == "not started":
            not_started += 1

        elif status == "ongoing":
            ongoing += 1

        elif "pause" in status or "stuck" in status:
            paused += 1

        elif "partial" in status:
            partial += 1

        elif "pending" in status:
            pending_client += 1

    return {
        "work_orders": len(rows),

        "not_started": not_started,

        "ongoing": ongoing,

        "paused_or_stuck": paused,

        "partial_completed": partial,

        "pending_client_details": pending_client,

        "open_work_orders":
            operations["open_work_orders"],

        "missing_execution_status":
            operations["missing_execution_status"],
    }