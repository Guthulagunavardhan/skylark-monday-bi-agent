import os
import streamlit as st
from dotenv import load_dotenv

from src.monday_client import MondayClient
from src.normalizer import (
    flatten_monday_items,
    normalize_deals,
    normalize_work_orders,
)
from src.agent import understand_query, build_answer


# --------------------------------------------------
# LOCAL ENVIRONMENT
# --------------------------------------------------

# Loads values from .env when running locally
load_dotenv()


# --------------------------------------------------
# STREAMLIT CLOUD SECRETS
# --------------------------------------------------

def load_streamlit_secrets_into_env():
    """
    Makes Streamlit Community Cloud secrets available through os.getenv().

    This means the same code works:
    - locally with .env
    - online with Streamlit Secrets
    """

    secret_names = [
        "MONDAY_API_TOKEN",
        "MONDAY_DEALS_BOARD_ID",
        "MONDAY_WORK_ORDERS_BOARD_ID",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
    ]

    try:
        for name in secret_names:

            # Keep local .env value if it already exists
            if os.getenv(name):
                continue

            # Otherwise read from Streamlit secrets
            if name in st.secrets:
                value = st.secrets[name]

                if value is not None and str(value).strip():
                    os.environ[name] = str(value)

    except Exception:
        # This is normal when running locally
        # without a Streamlit secrets.toml file
        pass


load_streamlit_secrets_into_env()


# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Skylark BI Agent",
    page_icon="📊",
    layout="wide",
)


st.title("Skylark Business Intelligence Agent")

st.caption(
    "Founder-level answers from live monday.com "
    "Deals + Work Orders boards"
)


# --------------------------------------------------
# OPENAI / FALLBACK MODE
# --------------------------------------------------

if not os.getenv("OPENAI_API_KEY"):
    st.info(
        "Running in BI fallback mode "
        "(no OpenAI API credits required)."
    )


# --------------------------------------------------
# REQUIRED SETTINGS CHECK
# --------------------------------------------------

required = [
    "MONDAY_API_TOKEN",
    "MONDAY_DEALS_BOARD_ID",
    "MONDAY_WORK_ORDERS_BOARD_ID",
]


missing = [
    key
    for key in required
    if not os.getenv(key)
]


if missing:

    st.error(
        "Missing environment variables / Streamlit secrets: "
        + ", ".join(missing)
    )

    st.stop()


# --------------------------------------------------
# LOAD LIVE MONDAY DATA
# --------------------------------------------------

@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def load_live_data():

    client = MondayClient()

    deals_board = int(
        os.environ[
            "MONDAY_DEALS_BOARD_ID"
        ]
    )

    work_orders_board = int(
        os.environ[
            "MONDAY_WORK_ORDERS_BOARD_ID"
        ]
    )

    # Read live monday boards
    deal_schema, deal_items = client.read_board(
        deals_board
    )

    wo_schema, wo_items = client.read_board(
        work_orders_board
    )

    # Flatten monday API response
    deal_rows = flatten_monday_items(
        deal_schema,
        deal_items,
    )

    wo_rows = flatten_monday_items(
        wo_schema,
        wo_items,
    )

    # Normalize imperfect source data
    deals, deal_warnings = normalize_deals(
        deal_rows
    )

    work_orders, wo_warnings = (
        normalize_work_orders(
            wo_rows
        )
    )

    warnings = (
        deal_warnings
        + wo_warnings
    )

    return (
        deals,
        work_orders,
        warnings,
    )


# --------------------------------------------------
# SAFE DATA LOAD
# --------------------------------------------------

try:

    with st.spinner(
        "Loading live monday.com data..."
    ):

        (
            deals,
            work_orders,
            warnings,
        ) = load_live_data()


except Exception as exc:

    st.error(
        f"Could not read monday.com: {exc}"
    )

    st.stop()


# --------------------------------------------------
# TOP METRICS
# --------------------------------------------------

c1, c2, c3 = st.columns(3)


c1.metric(
    "Deals loaded",
    len(deals),
)


c2.metric(
    "Work orders loaded",
    len(work_orders),
)


c3.metric(
    "Data warnings",
    len(warnings),
)


# --------------------------------------------------
# DATA QUALITY NOTES
# --------------------------------------------------

with st.expander(
    "Data quality notes"
):

    st.write(
        "The agent treats the source-sheet "
        "sentinels 8 (Deals) and 29 "
        "(Work Orders) as missing values "
        "where appropriate."
    )

    st.write(
        "Material data gaps are reported "
        "instead of silently being converted "
        "to zero."
    )

    if warnings:

        for warning in warnings[:20]:

            st.write(
                "•",
                warning,
            )

    else:

        st.write(
            "No additional normalization "
            "warnings were produced."
        )


# --------------------------------------------------
# CHAT SESSION
# --------------------------------------------------

if "messages" not in st.session_state:

    st.session_state.messages = []


# Display old messages
for msg in st.session_state.messages:

    with st.chat_message(
        msg["role"]
    ):

        st.markdown(
            msg["content"]
        )


# --------------------------------------------------
# CHAT INPUT
# --------------------------------------------------

question = st.chat_input(
    "Ask: How's our renewables pipeline looking this quarter?"
)


# --------------------------------------------------
# PROCESS QUESTION
# --------------------------------------------------

if question:

    # Save user question
    st.session_state.messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    with st.chat_message(
        "user"
    ):

        st.markdown(
            question
        )


    # Generate response
    with st.chat_message(
        "assistant"
    ):

        try:

            plan = understand_query(
                question
            )


            # ----------------------------------
            # CLARIFICATION
            # ----------------------------------

            if plan.get(
                "clarification"
            ):

                answer = plan[
                    "clarification"
                ]

                st.markdown(
                    answer
                )


            # ----------------------------------
            # BI ANSWER
            # ----------------------------------

            else:

                answer, facts = build_answer(
                    question,
                    plan,
                    deals,
                    work_orders,
                    warnings,
                )

                st.markdown(
                    answer
                )


                # Explainability
                with st.expander(
                    "How this answer was calculated"
                ):

                    st.json(
                        {
                            "query_plan": plan,
                            "facts": facts,
                        }
                    )


        # ----------------------------------
        # SAFE ERROR HANDLING
        # ----------------------------------

        except Exception as exc:

            answer = (
                "I couldn't complete that analysis "
                "because of an API or "
                "data-processing error: "
                f"`{exc}`"
            )

            st.error(
                answer
            )


    # Save assistant answer
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
        }
    )