import json
import os
import re
from datetime import date


SYSTEM = """
You are a business intelligence query planner for a founder.

Return ONLY valid JSON with these fields:

intent: one of
pipeline,
revenue,
operations,
collections,
sector_best_pipeline,
sector_best_revenue,
sector_best_receivables,
sector_detail,
sector_compare,
bottlenecks,
leadership_update,
smalltalk,
general

sector: string or null

compare_sectors: array of strings

period: one of this_quarter, all_time, null

needs_both_boards: boolean

clarification: string or null
"""


SECTORS = [
    "renewables",
    "mining",
    "railways",
    "powerline",
    "construction",
    "others",
    "dsp",
    "tender",
]


def _extract_sectors(question: str):
    q = question.lower()

    found = []

    for sector in SECTORS:
        if sector in q:
            pretty = (
                "DSP"
                if sector == "dsp"
                else sector.title()
            )

            if pretty not in found:
                found.append(pretty)

    return found


def _fallback_plan(question: str) -> dict:
    q = question.lower().strip()

    sectors_found = _extract_sectors(question)

    sector = (
        sectors_found[0]
        if len(sectors_found) == 1
        else None
    )

    if any(
        text in q
        for text in [
            "this quarter",
            "current quarter",
            "quarter",
        ]
    ):
        period = "this_quarter"
    else:
        period = "all_time"

    clarification = None

    # -------------------------
    # Sector comparisons
    # -------------------------

    if (
        any(
            word in q
            for word in [
                "compare",
                "versus",
                "vs",
                "difference between",
            ]
        )
        and len(sectors_found) >= 2
    ):
        intent = "sector_compare"

    # -------------------------
    # Incomplete sector comparison
    # -------------------------

    elif any(
        word in q
        for word in [
            "compare sectors",
            "compare sector",
            "compare",
            "versus",
            "vs",
        ]
    ) and len(sectors_found) < 2:
        intent = "sector_compare"

        clarification = (
            "Which two sectors would you like me to compare? "
            "For example: Compare Mining and Renewables."
        )

    # -------------------------
    # Best sectors
    # -------------------------

    elif (
        "sector" in q
        and any(
            text in q
            for text in [
                "strongest pipeline",
                "best pipeline",
                "highest pipeline",
                "largest pipeline",
            ]
        )
    ):
        intent = "sector_best_pipeline"

    elif (
        "sector" in q
        and any(
            text in q
            for text in [
                "highest revenue",
                "best revenue",
                "largest revenue",
                "highest contract value",
            ]
        )
    ):
        intent = "sector_best_revenue"

    elif (
        "sector" in q
        and any(
            text in q
            for text in [
                "most receivables",
                "highest receivables",
                "largest receivables",
                "highest outstanding",
            ]
        )
    ):
        intent = "sector_best_receivables"

    # -------------------------
    # Operational bottlenecks
    # -------------------------

    elif any(
        text in q
        for text in [
            "bottleneck",
            "bottlenecks",
            "operational issues",
            "operational problem",
            "operations problem",
            "where are we stuck",
            "where are work orders stuck",
        ]
    ):
        intent = "bottlenecks"

    # -------------------------
    # Leadership summary
    # -------------------------

    elif any(
        text in q
        for text in [
            "leadership update",
            "executive summary",
            "founder update",
            "leadership summary",
            "business summary",
            "overall business",
            "summary of everything",
        ]
    ):
        intent = "leadership_update"

    # -------------------------
    # Single-sector performance
    # -------------------------

    elif (
        len(sectors_found) == 1
        and any(
            text in q
            for text in [
                "performance",
                "summary",
                "overview",
                "how is",
                "show",
                "analyse",
                "analyze",
            ]
        )
    ):
        intent = "sector_detail"

    # -------------------------
    # Generic performance without sector
    # -------------------------

    elif any(
        text in q
        for text in [
            "show sector performance",
            "sector performance",
            "show performance",
            "performance overview",
        ]
    ):
        intent = "sector_detail"

        clarification = (
            "Which sector would you like me to analyze? "
            "For example: Mining, Renewables, Railways, "
            "Powerline, Construction, Tender, DSP, or Others."
        )

    # -------------------------
    # Collections
    # -------------------------

    elif any(
        text in q
        for text in [
            "collection",
            "collections",
            "collected",
            "receivable",
            "receivables",
            "outstanding",
        ]
    ):
        intent = "collections"

    # -------------------------
    # Operations
    # -------------------------

    elif any(
        text in q
        for text in [
            "work order",
            "work orders",
            "execution",
            "execution status",
            "operations",
            "operational",
            "wo status",
        ]
    ):
        intent = "operations"

    # -------------------------
    # Revenue
    # -------------------------

    elif any(
        text in q
        for text in [
            "revenue",
            "billing",
            "billed",
            "contract value",
            "amount to bill",
        ]
    ):
        intent = "revenue"

    # -------------------------
    # Pipeline
    # -------------------------

    elif any(
        text in q
        for text in [
            "pipeline",
            "deal",
            "deals",
            "closure",
            "deal stage",
        ]
    ):
        intent = "pipeline"

    # -------------------------
    # Small talk / unsupported
    # -------------------------

    else:
        intent = "smalltalk"

    return {
        "intent": intent,
        "sector": sector,
        "compare_sectors": sectors_found[:2],
        "period": period,
        "needs_both_boards": intent in {
            "sector_compare",
            "sector_detail",
            "leadership_update",
            "general",
        },
        "clarification": clarification,
    }


def understand_query(question: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")

    # No API key / no credits
    if not api_key:
        return _fallback_plan(question)

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key
        )

        model = os.getenv(
            "OPENAI_MODEL",
            "gpt-4.1-mini"
        )

        response = client.responses.create(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": SYSTEM
                },
                {
                    "role": "user",
                    "content": question
                }
            ]
        )

        text = response.output_text.strip()

        if text.startswith("```"):
            text = re.sub(
                r"^```(?:json)?\s*|\s*```$",
                "",
                text
            )

        result = json.loads(text)

        if "compare_sectors" not in result:
            result["compare_sectors"] = []

        return result

    except Exception:
        return _fallback_plan(question)


def quarter_bounds(today: date):
    quarter = (today.month - 1) // 3

    start_month = quarter * 3 + 1

    start = date(
        today.year,
        start_month,
        1
    )

    if start_month == 10:
        end = date(
            today.year,
            12,
            31
        )
    else:
        next_quarter = date(
            today.year,
            start_month + 3,
            1
        )

        end = date.fromordinal(
            next_quarter.toordinal() - 1
        )

    return start, end


def format_currency(value):
    if value is None:
        return "unknown"

    return f"₹{value / 10_000_000:.2f} Cr"


def _top_counts(counts, n=6):
    return sorted(
        counts.items(),
        key=lambda x: (-x[1], x[0])
    )[:n]


def _format_stage_summary(by_stage):
    if not by_stage:
        return "No active deal-stage data available."

    items = sorted(
        by_stage.items(),
        key=lambda x: (
            -x[1].get("value", 0),
            -x[1].get("count", 0)
        )
    )[:5]

    return ", ".join(
        (
            f"{stage}: "
            f"{metrics['count']} deals / "
            f"{format_currency(metrics['value'])}"
        )
        for stage, metrics in items
    )


def _sector_detail_answer(sector, facts):
    p = facts.get("pipeline")
    r = facts.get("revenue")
    o = facts.get("operations")
    c = facts.get("collections")

    lines = [
        f"**{sector} sector performance:**"
    ]

    if p:
        lines.append(
            (
                f"**Pipeline:** {p['active_deals']} active deals, "
                f"known pipeline value "
                f"**{format_currency(p['pipeline_value'])}**, "
                f"weighted pipeline "
                f"**{format_currency(p['weighted_pipeline'])}**."
            )
        )

    if r:
        lines.append(
            (
                f"**Revenue:** contract value ex-GST "
                f"**{format_currency(r['contract_value_ex_gst'])}**, "
                f"billed ex-GST "
                f"**{format_currency(r['billed_ex_gst'])}**, "
                f"amount still to bill "
                f"**{format_currency(r['to_bill_ex_gst'])}**."
            )
        )

    if c:
        lines.append(
            (
                f"**Collections:** collected incl. GST "
                f"**{format_currency(c['collected_inc_gst'])}**, "
                f"receivables "
                f"**{format_currency(c['receivable'])}**."
            )
        )

    if o:
        lines.append(
            (
                f"**Operations:** "
                f"{o['open_work_orders']} open and "
                f"{o['closed_work_orders']} closed work orders."
            )
        )

    if p:
        lines.append(
            (
                f"**Pipeline caveat:** "
                f"{p['missing_value_count']} active deals "
                f"lack deal value and "
                f"{p['missing_probability_count']} "
                f"lack closure probability."
            )
        )

    return "\n\n".join(lines)


def _compare_sector_answer(
    sector_a,
    sector_b,
    sector_data
):
    a = sector_data.get(sector_a)
    b = sector_data.get(sector_b)

    if not a or not b:
        return (
            "I couldn't calculate both sectors reliably. "
            "Please check the sector names."
        )

    a_pipe = a["pipeline"]
    b_pipe = b["pipeline"]

    a_rev = a["revenue"]
    b_rev = b["revenue"]

    a_col = a["collections"]
    b_col = b["collections"]

    a_ops = a["operations"]
    b_ops = b["operations"]

    pipeline_winner = (
        sector_a
        if a_pipe["pipeline_value"] >= b_pipe["pipeline_value"]
        else sector_b
    )

    revenue_winner = (
        sector_a
        if a_rev["contract_value_ex_gst"]
        >= b_rev["contract_value_ex_gst"]
        else sector_b
    )

    receivable_higher = (
        sector_a
        if a_col["receivable"] >= b_col["receivable"]
        else sector_b
    )

    return (
        f"**{sector_a} vs {sector_b}:**\n\n"
        f"**Pipeline:** {sector_a} "
        f"{format_currency(a_pipe['pipeline_value'])} vs "
        f"{sector_b} "
        f"{format_currency(b_pipe['pipeline_value'])}. "
        f"**{pipeline_winner} has the larger known active pipeline.**\n\n"
        f"**Contract value ex-GST:** {sector_a} "
        f"{format_currency(a_rev['contract_value_ex_gst'])} vs "
        f"{sector_b} "
        f"{format_currency(b_rev['contract_value_ex_gst'])}. "
        f"**{revenue_winner} is higher.**\n\n"
        f"**Receivables:** {sector_a} "
        f"{format_currency(a_col['receivable'])} vs "
        f"{sector_b} "
        f"{format_currency(b_col['receivable'])}. "
        f"**{receivable_higher} currently carries more receivables.**\n\n"
        f"**Open work orders:** {sector_a} "
        f"{a_ops['open_work_orders']} vs "
        f"{sector_b} "
        f"{b_ops['open_work_orders']}.\n\n"
        f"Comparison is performed at **sector level across the two boards**. "
        f"It does not assume an unreliable row-by-row join between "
        f"Deals and Work Orders."
    )


def _fallback_answer(
    question,
    plan,
    facts,
    data_warnings
):
    clarification = plan.get("clarification")

    if clarification:
        return clarification

    intent = plan.get("intent")

    # -----------------------
    # SMALL TALK
    # -----------------------

    if intent == "smalltalk":
        q = question.lower().strip()

        if any(
            text in q
            for text in [
                "how are you",
                "how r u",
                "hello",
                "hi",
                "hey",
                "good morning",
                "good afternoon",
                "good evening",
            ]
        ):
            return (
                "I'm doing well. You can ask me about "
                "pipeline, revenue, work orders, collections, "
                "sector performance, operational bottlenecks, "
                "or request a leadership update."
            )

        return (
            "I’m designed to answer business-intelligence questions "
            "using the live Deals and Work Orders boards. "
            "Try asking about pipeline, revenue, operations, "
            "collections, sectors, or leadership performance."
        )

    # -----------------------
    # PIPELINE
    # -----------------------

    if intent == "pipeline":
        p = facts.get("pipeline")

        if not p:
            return "Pipeline data could not be calculated."

        stage_text = _format_stage_summary(
            p["by_stage"]
        )

        return (
            f"**Pipeline summary:** "
            f"{p['active_deals']} active deals with "
            f"**{format_currency(p['pipeline_value'])}** "
            f"known pipeline value.\n\n"
            f"Weighted pipeline is "
            f"**{format_currency(p['weighted_pipeline'])}** "
            f"using only deals where both value and "
            f"closure probability are available.\n\n"
            f"**Top active stages:** {stage_text}.\n\n"
            f"**Data caveat:** "
            f"{p['missing_value_count']} active deals "
            f"are missing deal value and "
            f"{p['missing_probability_count']} "
            f"are missing closure probability."
        )

    # -----------------------
    # REVENUE
    # -----------------------

    if intent == "revenue":
        r = facts.get("revenue")

        if not r:
            return "Revenue data could not be calculated."

        return (
            f"**Revenue summary:** "
            f"{r['work_orders']} work orders.\n\n"
            f"Contract value ex-GST: "
            f"**{format_currency(r['contract_value_ex_gst'])}**\n\n"
            f"Billed ex-GST: "
            f"**{format_currency(r['billed_ex_gst'])}**\n\n"
            f"Amount still to bill ex-GST: "
            f"**{format_currency(r['to_bill_ex_gst'])}**\n\n"
            f"Collected incl. GST: "
            f"**{format_currency(r['collected_inc_gst'])}**"
        )

    # -----------------------
    # OPERATIONS
    # -----------------------

    if intent == "operations":
        o = facts.get("operations")

        if not o:
            return "Work-order data could not be calculated."

        execution_text = ", ".join(
            f"{name}: {count}"
            for name, count
            in _top_counts(
                o["execution_status_counts"]
            )
        )

        return (
            f"**Work-order status:** "
            f"{o['work_orders']} total work orders.\n\n"
            f"**{o['open_work_orders']} are open** and "
            f"**{o['closed_work_orders']} are closed** "
            f"based on WO Status (billed).\n\n"
            f"**Execution status breakdown:** "
            f"{execution_text}.\n\n"
            f"**Data caveat:** "
            f"{o['missing_execution_status']} records "
            f"are missing execution status and "
            f"{o['missing_wo_status']} records "
            f"are missing WO status."
        )

    # -----------------------
    # COLLECTIONS
    # -----------------------

    if intent == "collections":
        c = facts.get("collections")

        if not c:
            return "Collection data could not be calculated."

        return (
            f"**Collection summary:**\n\n"
            f"Collected amount incl. GST: "
            f"**{format_currency(c['collected_inc_gst'])}**\n\n"
            f"Current receivables: "
            f"**{format_currency(c['receivable'])}**\n\n"
            f"**{c['accounts_with_receivable']} "
            f"work-order records currently have "
            f"a positive receivable amount.\n\n"
            f"**Data caveat:** "
            f"{c['missing_collection_amount']} records "
            f"have no collected-amount value and "
            f"{c['missing_receivable']} records "
            f"have no receivable value."
        )

    # -----------------------
    # BEST PIPELINE SECTOR
    # -----------------------

    if intent == "sector_best_pipeline":
        s = facts.get("best_pipeline_sector")

        if not s:
            return (
                "I couldn't determine the strongest "
                "pipeline sector."
            )

        return (
            f"**{s['sector']} has the strongest known active pipeline** "
            f"at **{format_currency(s['pipeline_value'])}** "
            f"across {s['active_deals']} active deals.\n\n"
            f"Weighted pipeline is "
            f"**{format_currency(s['weighted_pipeline'])}**.\n\n"
            f"**Caveat:** this ranking uses known deal values only. "
            f"{s['missing_value_count']} active deals in this sector "
            f"lack deal value."
        )

    # -----------------------
    # BEST REVENUE SECTOR
    # -----------------------

    if intent == "sector_best_revenue":
        s = facts.get("best_revenue_sector")

        if not s:
            return (
                "I couldn't determine the highest-revenue sector."
            )

        return (
            f"**{s['sector']} has the highest work-order contract value** "
            f"at **{format_currency(s['contract_value_ex_gst'])} "
            f"ex-GST**.\n\n"
            f"Billed ex-GST is "
            f"**{format_currency(s['billed_ex_gst'])}**, "
            f"with "
            f"**{format_currency(s['to_bill_ex_gst'])}** "
            f"remaining to bill."
        )

    # -----------------------
    # BEST RECEIVABLE SECTOR
    # -----------------------

    if intent == "sector_best_receivables":
        s = facts.get("best_receivable_sector")

        if not s:
            return (
                "I couldn't determine the sector with "
                "the highest receivables."
            )

        return (
            f"**{s['sector']} currently has the highest receivables** "
            f"at **{format_currency(s['receivable'])}**.\n\n"
            f"{s['accounts_with_receivable']} work-order records "
            f"in this sector have a positive receivable amount."
        )

    # -----------------------
    # SINGLE SECTOR DETAIL
    # -----------------------

    if intent == "sector_detail":
        sector = plan.get("sector")

        if not sector:
            return (
                "Which sector would you like me to analyze?"
            )

        return _sector_detail_answer(
            sector,
            facts
        )

    # -----------------------
    # SECTOR COMPARISON
    # -----------------------

    if intent == "sector_compare":
        compare_sectors = plan.get(
            "compare_sectors",
            []
        )

        if len(compare_sectors) < 2:
            return (
                "Which two sectors would you like me to compare?"
            )

        return _compare_sector_answer(
            compare_sectors[0],
            compare_sectors[1],
            facts.get(
                "sector_performance",
                {}
            )
        )

    # -----------------------
    # BOTTLENECKS
    # -----------------------

    if intent == "bottlenecks":
        b = facts.get("bottlenecks")

        if not b:
            return (
                "Operational bottlenecks could not be calculated."
            )

        return (
            f"**Operational bottlenecks:**\n\n"
            f"- Not started: **{b['not_started']}**\n"
            f"- Ongoing: **{b['ongoing']}**\n"
            f"- Paused or stuck: **{b['paused_or_stuck']}**\n"
            f"- Partially completed: **{b['partial_completed']}**\n"
            f"- Pending client details: "
            f"**{b['pending_client_details']}**\n\n"
            f"There are also "
            f"**{b['open_work_orders']} open work orders**.\n\n"
            f"**Data caveat:** "
            f"{b['missing_execution_status']} records "
            f"are missing execution status."
        )

    # -----------------------
    # LEADERSHIP / GENERAL
    # -----------------------

    lines = [
        "**Leadership BI update**"
    ]

    if "pipeline" in facts:
        p = facts["pipeline"]

        lines.append(
            (
                f"**Pipeline:** "
                f"{p['active_deals']} active deals; "
                f"known value "
                f"**{format_currency(p['pipeline_value'])}**; "
                f"weighted pipeline "
                f"**{format_currency(p['weighted_pipeline'])}**."
            )
        )

    if "revenue" in facts:
        r = facts["revenue"]

        lines.append(
            (
                f"**Revenue:** contract value ex-GST "
                f"**{format_currency(r['contract_value_ex_gst'])}**; "
                f"billed ex-GST "
                f"**{format_currency(r['billed_ex_gst'])}**; "
                f"still to bill "
                f"**{format_currency(r['to_bill_ex_gst'])}**."
            )
        )

    if "operations" in facts:
        o = facts["operations"]

        lines.append(
            (
                f"**Operations:** "
                f"{o['work_orders']} work orders; "
                f"{o['open_work_orders']} open; "
                f"{o['closed_work_orders']} closed."
            )
        )

    if "collections" in facts:
        c = facts["collections"]

        lines.append(
            (
                f"**Collections:** collected incl. GST "
                f"**{format_currency(c['collected_inc_gst'])}**; "
                f"receivables "
                f"**{format_currency(c['receivable'])}**."
            )
        )

    if "bottlenecks" in facts:
        b = facts["bottlenecks"]

        lines.append(
            (
                f"**Attention areas:** "
                f"{b['not_started']} not-started, "
                f"{b['paused_or_stuck']} paused/stuck, and "
                f"{b['pending_client_details']} pending-client-detail "
                f"work orders."
            )
        )

    lines.append(
        (
            "**Interpretation note:** this is a current-state summary. "
            "The available data does not support reliable week-over-week "
            "trend claims without historical snapshots."
        )
    )

    return "\n\n".join(lines)


def build_answer(
    question,
    plan,
    deals,
    work_orders,
    data_warnings
):
    from .metrics import (
        pipeline_summary,
        revenue_summary,
        operations_summary,
        collection_summary,
        sector_performance,
        strongest_pipeline_sector,
        highest_revenue_sector,
        highest_receivable_sector,
        operational_bottlenecks,
    )

    sector = plan.get("sector")
    period = plan.get("period")

    start = None
    end = None

    if period == "this_quarter":
        start, end = quarter_bounds(
            date.today()
        )

    intent = plan.get(
        "intent",
        "smalltalk"
    )

    facts = {}

    # -------------------------
    # Core summaries
    # -------------------------

    if intent in {
        "pipeline",
        "leadership_update",
        "general",
        "sector_detail",
    }:
        facts["pipeline"] = pipeline_summary(
            deals,
            sector,
            start,
            end
        )

    if intent in {
        "revenue",
        "leadership_update",
        "general",
        "sector_detail",
    }:
        facts["revenue"] = revenue_summary(
            work_orders,
            sector
        )

    if intent in {
        "operations",
        "leadership_update",
        "general",
        "sector_detail",
    }:
        facts["operations"] = operations_summary(
            work_orders,
            sector
        )

    if intent in {
        "collections",
        "leadership_update",
        "general",
        "sector_detail",
    }:
        facts["collections"] = collection_summary(
            work_orders,
            sector
        )

    # -------------------------
    # Sector intelligence
    # -------------------------

    if intent == "sector_best_pipeline":
        facts["best_pipeline_sector"] = (
            strongest_pipeline_sector(
                deals
            )
        )

    if intent == "sector_best_revenue":
        facts["best_revenue_sector"] = (
            highest_revenue_sector(
                work_orders
            )
        )

    if intent == "sector_best_receivables":
        facts["best_receivable_sector"] = (
            highest_receivable_sector(
                work_orders
            )
        )

    if intent == "sector_compare":
        facts["sector_performance"] = (
            sector_performance(
                deals,
                work_orders
            )
        )

    # -------------------------
    # Bottlenecks
    # -------------------------

    if intent in {
        "bottlenecks",
        "leadership_update",
        "general",
    }:
        facts["bottlenecks"] = (
            operational_bottlenecks(
                work_orders,
                sector
            )
        )

    # -------------------------
    # No-credit fallback
    # -------------------------

    api_key = os.getenv(
        "OPENAI_API_KEY"
    )

    if not api_key:
        return (
            _fallback_answer(
                question,
                plan,
                facts,
                data_warnings
            ),
            facts
        )

    # -------------------------
    # OpenAI mode if enabled later
    # -------------------------

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=api_key
        )

        model = os.getenv(
            "OPENAI_MODEL",
            "gpt-4.1-mini"
        )

        prompt = f"""
Question:
{question}

Interpreted query plan:
{json.dumps(plan, indent=2)}

Authoritative calculated facts:
{json.dumps(facts, indent=2)}

Data warnings:
{json.dumps(data_warnings, indent=2)}

Write a concise founder-level BI answer.

Rules:
- Use only the calculated facts.
- Never invent numbers.
- Never invent historical trends.
- Clearly state material data caveats.
- If the question is ambiguous, ask for clarification.
"""

        response = client.responses.create(
            model=model,
            input=prompt
        )

        return (
            response.output_text,
            facts
        )

    except Exception:
        return (
            _fallback_answer(
                question,
                plan,
                facts,
                data_warnings
            ),
            facts
        )