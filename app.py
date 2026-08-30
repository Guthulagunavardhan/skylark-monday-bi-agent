import os
import streamlit as st
from dotenv import load_dotenv

from src.monday_client import MondayClient
from src.normalizer import flatten_monday_items, normalize_deals, normalize_work_orders
from src.agent import understand_query, build_answer

load_dotenv()

st.set_page_config(
    page_title="Skylark BI Agent",
    page_icon="📊",
    layout="wide",
)

st.title("Skylark Business Intelligence Agent")
st.caption("Founder-level answers from live monday.com Deals + Work Orders boards")

if not os.getenv("OPENAI_API_KEY"):
    st.info("Running in BI fallback mode (no OpenAI API credits required).")

required = [
    "MONDAY_API_TOKEN",
    "MONDAY_DEALS_BOARD_ID",
    "MONDAY_WORK_ORDERS_BOARD_ID",
]
missing = [k for k in required if not os.getenv(k)]
if missing:
    st.error("Missing environment variables: " + ", ".join(missing))
    st.stop()

@st.cache_data(ttl=300, show_spinner=False)
def load_live_data():
    client = MondayClient()
    deals_board = int(os.environ["MONDAY_DEALS_BOARD_ID"])
    wo_board = int(os.environ["MONDAY_WORK_ORDERS_BOARD_ID"])

    deal_schema, deal_items = client.read_board(deals_board)
    wo_schema, wo_items = client.read_board(wo_board)

    deal_rows = flatten_monday_items(deal_schema, deal_items)
    wo_rows = flatten_monday_items(wo_schema, wo_items)

    deals, deal_warnings = normalize_deals(deal_rows)
    work_orders, wo_warnings = normalize_work_orders(wo_rows)

    return deals, work_orders, deal_warnings + wo_warnings

try:
    deals, work_orders, warnings = load_live_data()
except Exception as exc:
    st.error(f"Could not read monday.com: {exc}")
    st.stop()

c1, c2, c3 = st.columns(3)
c1.metric("Deals loaded", len(deals))
c2.metric("Work orders loaded", len(work_orders))
c3.metric("Data warnings", len(warnings))

with st.expander("Data quality notes"):
    st.write(
        "The agent treats the source-sheet sentinels 8 (Deals) and 29 "
        "(Work Orders) as missing values where appropriate, and reports "
        "material data gaps instead of silently converting them to zero."
    )
    for warning in warnings[:20]:
        st.write("•", warning)

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

question = st.chat_input(
    "Ask: How's our renewables pipeline looking this quarter?"
)

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            plan = understand_query(question)
            if plan.get("clarification"):
                answer = plan["clarification"]
                st.markdown(answer)
            else:
                answer, facts = build_answer(
                    question, plan, deals, work_orders, warnings
                )
                st.markdown(answer)
                with st.expander("How this answer was calculated"):
                    st.json({"query_plan": plan, "facts": facts})
        except Exception as exc:
            answer = (
                "I couldn't complete that analysis because of an API or "
                f"data-processing error: `{exc}`"
            )
            st.error(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
