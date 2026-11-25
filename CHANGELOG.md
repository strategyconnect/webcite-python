# Changelog

All notable changes to this package are recorded here. The project follows
[semantic versioning](https://semver.org/).

## 0.1.0 (unreleased)

First version.

- `Webcite` and `AsyncWebcite` clients over `httpx` for every operation in the public OpenAPI
  document (28 operations) plus the credit balance route (29 methods in all).
- API key from `api_key=` or `WEBCITE_API_KEY`; base URL from `base_url=` or `WEBCITE_API_URL`.
- Typed errors carrying the server's message, a next step and a documentation link.
- Retries with backoff for GET requests and keyed verifications on 429 and 5xx only.
- 15-minute default timeout for long extractions; `wait_for_ask()` polling helper.
- Verification streaming that fails loudly when the stream ends without a result and `done`.
- No telemetry.
