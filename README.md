# Skylark Drones — monday.com Business Intelligence Agent

A read-only conversational BI agent that dynamically queries monday.com Deals
and Work Orders boards, normalizes messy business data, calculates deterministic
metrics, and uses an LLM to present founder-level insights.

## Architecture

Founder -> Streamlit chat -> Query planner (LLM) -> deterministic BI metrics
-> live monday.com GraphQL data -> executive response

The LLM interprets questions and explains calculated facts. It does **not**
invent or directly calculate financial metrics.

## Why this design

- **Read-only monday integration:** no mutations are used.
- **Dynamic:** no CSV rows are hardcoded into the app.
- **Resilient:** source-specific missing-value sentinels are normalized.
- **Auditable:** the UI exposes the query plan and metric facts.
- **Fast to deploy:** one Streamlit service.

## Source-data findings

From the supplied assignment files:

- Work Orders: 176 data rows, 38 columns.
- Deals: 346 source rows, 12 columns.
- Deals frequently uses `8` as a missing-value placeholder.
- Work Orders frequently uses `29` as a missing-value placeholder.
- Deals contains two malformed repeated-header-like rows that should not count
  as business records.
- Important revenue/probability fields have substantial missingness, so the
  agent reports coverage caveats rather than treating unknown as zero.

## monday.com setup

Create two separate boards:

1. Deals
2. Work Orders

Import the supplied spreadsheets. Keep the column titles unchanged for the MVP
because normalization maps fields by title.

After import, copy each board ID from the monday.com board URL and set:

```env
MONDAY_DEALS_BOARD_ID=...
MONDAY_WORK_ORDERS_BOARD_ID=...
```

Create a monday API token with read access to the boards and set:

```env
MONDAY_API_TOKEN=...
```

## Local run

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

## Recommended test questions

- How's our renewables pipeline looking this quarter?
- What is the total open pipeline for mining?
- Which stages hold most of our active pipeline?
- How much have we billed and collected in powerline work orders?
- What operational or data-quality risks should leadership know about?
- Prepare a leadership update for the business.

## Deployment

Deploy the repository to Streamlit Community Cloud (or Render).
Set the five environment variables as deployment secrets.

## Security

Never commit `.env` or the monday/OpenAI tokens.
The application performs only GraphQL reads against monday.com.
