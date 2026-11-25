Fixtures used by the tests. No test calls the live API.

- `claim-*.json`, `doc-*.json`: saved real responses published by Webcite at
  https://webcite.co/samples/ (verify and extract).
- `openapi.json`: the public OpenAPI document from https://api.webcite.co/api/v1/openapi.json,
  saved on 25 November 2026. `make update-openapi` refreshes it.
- `balance.json`: the field layout returned by the credit balance route on 25 November 2026,
  with the account's numbers replaced.
