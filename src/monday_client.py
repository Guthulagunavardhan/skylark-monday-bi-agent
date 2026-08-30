import os
import requests

API_URL = "https://api.monday.com/v2"

class MondayClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("MONDAY_API_TOKEN")
        if not self.token:
            raise ValueError("MONDAY_API_TOKEN is missing")

    @property
    def headers(self):
        return {
            "Authorization": self.token,
            "Content-Type": "application/json",
        }

    def _post(self, query: str, variables: dict | None = None) -> dict:
        response = requests.post(
            API_URL,
            json={"query": query, "variables": variables or {}},
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("errors"):
            raise RuntimeError(body["errors"])
        return body["data"]

    def get_board_schema(self, board_id: int) -> dict:
        query = """
        query ($board_id: [ID!]!) {
          boards(ids: $board_id) {
            id
            name
            columns {
              id
              title
              type
            }
          }
        }
        """
        data = self._post(query, {"board_id": [str(board_id)]})
        if not data["boards"]:
            raise ValueError(f"Board {board_id} not found or not accessible")
        return data["boards"][0]

    def get_all_items(self, board_id: int, page_size: int = 500) -> list[dict]:
        initial_query = """
        query ($board_id: [ID!]!, $limit: Int!) {
          boards(ids: $board_id) {
            items_page(limit: $limit) {
              cursor
              items {
                id
                name
                column_values {
                  id
                  text
                  value
                  type
                }
              }
            }
          }
        }
        """
        data = self._post(initial_query, {
            "board_id": [str(board_id)],
            "limit": page_size
        })
        page = data["boards"][0]["items_page"]
        items = list(page["items"])
        cursor = page["cursor"]

        next_query = """
        query ($cursor: String!, $limit: Int!) {
          next_items_page(cursor: $cursor, limit: $limit) {
            cursor
            items {
              id
              name
              column_values {
                id
                text
                value
                type
              }
            }
          }
        }
        """
        while cursor:
            data = self._post(next_query, {
                "cursor": cursor,
                "limit": page_size
            })
            page = data["next_items_page"]
            items.extend(page["items"])
            cursor = page["cursor"]

        return items

    def read_board(self, board_id: int) -> tuple[dict, list[dict]]:
        schema = self.get_board_schema(board_id)
        items = self.get_all_items(board_id)
        return schema, items
