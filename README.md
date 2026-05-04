## **Logs narrate; IntentProof gives you proof.**

**IntentProof** is **auditable execution records** for actions that must be defensible—**intent** tied to what actually ran.

**Wrap** the calls that matter; each invocation emits one **verifiable** **`ExecutionEvent`**, structured so intent and outcome can be **reconciled** with reality—not only observed.

Observability captures what happened. **IntentProof** tells you whether it matched what was **meant to happen**.

Every **`ExecutionEvent`** contains:

- **`intent`**: what this invocation was meant to prove
- **`action`**: the stable operation id for this step
- **`status`**: success or error
- **`inputs`** and **`output`**: what the runtime saw going in and coming out

## Why this matters

Modern systems—especially AI agents—do not only compute; they act:
issuing refunds, sending emails, updating databases.

When something goes wrong, logs tell you what ran.
They don't tell you:

- what was supposed to happen
- whether all steps completed
- whether systems ended up in a consistent state

**IntentProof** exists to bridge that gap.

It records intent alongside execution so systems can be verified, not just observed.

### Picture this:

It's 4:47 on a Friday. A customer insists the critical action never happened. Support sees scattered traces; engineering sees green checks; finance asks for **one** clean chain: what was **supposed** to occur, what **did** occur, and whether the outcome is **complete**.

Ordinary telemetry shows that *something ran*. It rarely ships an **auditable story** you can hand to someone who doesn't read your codebase. **IntentProof** exists for when the question stops being "what was logged?" and starts being **"prove it."**

## Requirements

- **Python** 3.11 or newer

## Install

**Package:** `intentproof-sdk` (PyPI).

- [PyPI — `intentproof-sdk`](https://pypi.org/project/intentproof-sdk/)
- [GitHub Releases — IntentProof Python SDK](https://github.com/intentproof/intentproof-sdk-python/releases)

Pin the **version** you want from PyPI or from GitHub Releases. Replace **`x.y.z`** below with that version.

```bash
pip install intentproof-sdk==x.y.z
```

## Quick start

```python
from intentproof import client

refund = client.wrap(
    intent="Initiate refund",
    action="stripe.refunds.create",
    fn=lambda inp: stripe_refunds_create(inp),
)
```

Each refund call emits one **`ExecutionEvent`** with the **`intent`** and **`action`** you chose, the **`inputs`** and **`output`** (or **`error`** + **`status: "error"`**), and timing fields—an execution record you can inspect, export, or verify later.

## Reference

Detailed tables for the client API, emitted events, configuration, and related exports.

### `IntentProofClient` API

| Member | Description |
| ------ | ----------- |
| **`__init__(config=None)`** | Creates a client. Default exporters: a single **`MemoryExporter`** if you omit **`config.exporters`**. |
| **`configure(config)`** | Re-applies **`IntentProofConfig`** fields (exporters, error hook, defaults, stack policy). |
| **`wrap(...)`** | Returns a callable that records one **`ExecutionEvent`** per invocation (sync or async). Options must satisfy **`assert_wrap_options_shape`** (`intent` / `action` non-empty strings, etc.). |
| **`flush()`** | Awaits **`flush()`** on every **`Exporter`** that implements it, in parallel. |
| **`shutdown()`** | For each **`Exporter`**, awaits **`shutdown()`** if implemented, otherwise **`flush()`** if implemented. |
| **`get_correlation_id()`** | Returns the correlation ID from **contextvars** (or equivalent), if any. |
| **`with_correlation(fn)`** | Runs **`fn`** with a **fresh UUID** as correlation ID for nested wraps. |
| **`with_correlation(id, fn)`** | Runs **`fn`** with **`id`** stripped; blank / whitespace-only **`id`** falls back to a UUID. |

#### Module-level helpers (same package as the client)

These use the same correlation context as **`IntentProofClient`** instances:

| Export | Description |
| ------ | ----------- |
| **`create_intent_proof_client(config=None)`** | New isolated client (tests, workers, multi-tenant). |
| **`get_intent_proof_client()`** | Lazy singleton used by **`client`**. |
| **`client`** | Default singleton instance. |
| **`get_correlation_id()`** | Same behavior as the instance method. |
| **`run_with_correlation_id(id, fn)`** | Requires a **non-empty** correlation ID after strip; raises if invalid. |
| **`assert_correlation_id(id)`** | Runtime assertion for correlation ID shape. |
| **`assert_wrap_options_shape(options)`** | Runtime validation for **`WrapOptions`**. |

### `ExecutionEvent` fields

| Field | Description |
| ----- | ----------- |
| **`id`** | Unique event id (UUID). |
| **`correlationId`** | Request or trace correlation ID when present—usually from context or **`WrapOptions`**. |
| **`intent`** | Human-readable label for what this invocation is meant to prove (outcome, policy goal, or domain). |
| **`action`** | Stable operation id for this step (often dotted or namespaced). |
| **`inputs`** | JSON-safe snapshot of call arguments (default) or **`capture_input`** result. |
| **`output`** | JSON-safe return value or **`capture_output`** result on success. When **`status`** is **`"error"`**, set only if **`capture_error`** returned a value. |
| **`error`** | On failure: **`name`**, **`message`**, and optional **`stack`** (see **`include_error_stack`**). |
| **`status`** | **`"ok"`** if the wrapped call completed normally; **`"error"`** if it raised. |
| **`startedAt`** | Start time (ISO 8601). |
| **`completedAt`** | Completion time (ISO 8601). |
| **`durationMs`** | Wall time between start and completion, in milliseconds. |
| **`attributes`** | Optional plain mapping (string / number / boolean values only), merged from client defaults and wrap options. |

### `WrapOptions` and `IntentProofConfig`

#### `WrapOptions` (passed to **`wrap`**)

| Field | Description |
| ----- | ----------- |
| **`intent`**, **`action`** | Required, non-empty after strip. |
| **`correlationId`** | Optional; when set, non-empty after strip. Otherwise the active correlation ID from context is used, if any. |
| **`attributes`** | Per-invocation dimensions merged over **`default_attributes`**. |
| **`capture_input`**, **`capture_output`**, **`capture_error`** | Optional hooks to replace default **`snapshot`** behavior for inputs, success output, or error-side extra **`output`**. |
| **`include_error_stack`** | When `False`, omit **`error.stack`** for this wrap (overrides client default). |
| **`max_depth`**, **`max_keys`**, **`redact_keys`**, **`max_string_length`** | Forwarded to **`snapshot`** for inputs and outputs (see **`SerializeOptions`** in type hints). |

#### `IntentProofConfig` (`__init__` / **`configure`**)

| Field | Description |
| ----- | ----------- |
| **`exporters`** | Ordered list of **`Exporter`** instances; each receives every **`ExecutionEvent`**. |
| **`on_exporter_error`** | Called when any exporter’s **`export()`** raises or returns a failed future. Defaults to **`logging`** / stderr. |
| **`default_attributes`** | Merged into every event’s **`attributes`** (wrap-specific attributes win on key collision). |
| **`include_error_stack`** | Default `True`; set `False` in production if stacks must not leave the trust zone. |

### Related exports

- **`MemoryExporter`**, **`HttpExporter`**, **`BoundedQueueExporter`** — Delivery implementations; each implements **`Exporter`**.
- **`snapshot`** — Same JSON-safe serializer the client uses internally, if you build custom tooling.
- **`VERSION`** — Package version string (e.g. from importlib metadata at runtime).

---

## Examples

### 1 — Refund and customer receipt

Support approves **order `ORD-1042`**. Your service creates the **Stripe refund**, then emails the customer a receipt. **`run_with_correlation_id`** ties both calls to **`req_refund_ord_1042`**. Each **`wrap`** defines its own **`intent`** (the outcome you are proving for that step) and **`action`** (how it is done); **`correlationId`** is what stitches them together.

**`capture_input`** / **`capture_output`** trim each record to the fields you want in proof (refund id, amounts, message id)—not full vendor payloads.

JSON on the wire uses **camelCase**; Python **`wrap`** options use **snake_case** (e.g. **`capture_input`**).

```python
from intentproof import client, run_with_correlation_id

create_refund = client.wrap(
    intent="Return captured funds to the customer's original card network",
    action="stripe.refund.create",
    attributes={"vendor": "stripe", "step": "refund_money"},
    capture_input=lambda args: {
        "paymentIntentId": args[0]["paymentIntentId"],
        "amountCents": args[0]["amountCents"],
        "reason": args[0].get("reason"),
    },
    capture_output=lambda result: {
        "refundId": result["id"],
        "status": result["status"],
        "amountCents": result["amountCents"],
    },
    fn=lambda inp: {
        "id": "re_3SAMPLEabcdefghijklmnop",
        "status": "succeeded",
        "amountCents": inp["amountCents"],
    },
)

send_refund_receipt = client.wrap(
    intent="Deliver a customer-visible refund confirmation for the ledger entry",
    action="email.customer.refund_receipt",
    attributes={"channel": "email", "step": "notify_customer"},
    capture_input=lambda args: {
        "customerId": args[0]["customerId"],
        "orderId": args[0]["orderId"],
        "refundId": args[0]["refundId"],
        "amountCents": args[0]["amountCents"],
    },
    capture_output=lambda result: {
        "messageId": result["messageId"],
        "status": result["status"],
    },
    fn=lambda p: {"messageId": "msg_49401_sample", "status": "queued"},
)


def refund_flow():
    with run_with_correlation_id("req_refund_ord_1042"):
        refund = create_refund(
            {
                "paymentIntentId": "pi_3SAMPLEabcdefghijklmnop",
                "amountCents": 4999,
                "reason": "requested_by_customer",
            }
        )
        send_refund_receipt(
            {
                "customerId": "cus_SAMPLEabcdefghijkl",
                "orderId": "ORD-1042",
                "refundId": refund["id"],
                "amountCents": refund["amountCents"],
            }
        )
```

Emitted **`ExecutionEvent`** values (same **`correlationId`** on each; distinct **`intent`** per step; **`id`** / timestamps omitted):

```json
[
  {
    "correlationId": "req_refund_ord_1042",
    "intent": "Return captured funds to the customer's original card network",
    "action": "stripe.refund.create",
    "inputs": {
      "paymentIntentId": "pi_3SAMPLEabcdefghijklmnop",
      "amountCents": 4999,
      "reason": "requested_by_customer"
    },
    "status": "ok",
    "output": {
      "refundId": "re_3SAMPLEabcdefghijklmnop",
      "status": "succeeded",
      "amountCents": 4999
    },
    "attributes": {
      "service": "billing-api",
      "env": "test",
      "vendor": "stripe",
      "step": "refund_money"
    }
  },
  {
    "correlationId": "req_refund_ord_1042",
    "intent": "Deliver a customer-visible refund confirmation for the ledger entry",
    "action": "email.customer.refund_receipt",
    "inputs": {
      "customerId": "cus_SAMPLEabcdefghijkl",
      "orderId": "ORD-1042",
      "refundId": "re_3SAMPLEabcdefghijklmnop",
      "amountCents": 4999
    },
    "status": "ok",
    "output": { "messageId": "msg_49401_sample", "status": "queued" },
    "attributes": {
      "service": "billing-api",
      "env": "test",
      "channel": "email",
      "step": "notify_customer"
    }
  }
]
```

### 2 — Payment failure with operator metadata (`capture_error`)

When a capture **raises**, the record still carries **`status: "error"`** and **`error.message`** for proof of failure. **`capture_error`** adds a small, JSON-safe **`output`** for dashboards (e.g. decline code) without pretending the business call succeeded.

```python
def decline_card(_input):
    raise RuntimeError("Your card was declined.")


capture_payment = client.wrap(
    intent="Capture authorized funds",
    action="stripe.payment_intent.capture",
    capture_input=lambda args: {"paymentIntentId": args[0]["paymentIntentId"]},
    capture_error=lambda _err: {"code": "card_declined", "retryable": False},
    fn=decline_card,
)

try:
    capture_payment({"paymentIntentId": "pi_3SAMPLEabcdefghijklmnop"})
except RuntimeError:
    pass  # card declined — expected
```

```json
{
  "intent": "Capture authorized funds",
  "action": "stripe.payment_intent.capture",
  "inputs": { "paymentIntentId": "pi_3SAMPLEabcdefghijklmnop" },
  "status": "error",
  "error": {
    "name": "RuntimeError",
    "message": "Your card was declined."
  },
  "output": { "code": "card_declined", "retryable": false }
}
```

### 3 — Proof delivery over HTTP (same **`ExecutionEvent`** shape)

**`HttpExporter`** POSTs the same **`ExecutionEvent`** your verifiers see in memory—here alongside **`MemoryExporter`** so tests can assert the wire without a real collector. The request omits ambient credentials; the body is **`{ "intentproof": "1", "event": … }`** (see exporter implementation). For authenticated collectors, pass **`headers`** (e.g. **`Authorization`**, API keys) — see [Security](#security).

```python
run_probe = client.wrap(intent="HTTP test", action="test.http", fn=lambda: 42)
run_probe()
```

```json
{
  "intent": "HTTP test",
  "action": "test.http",
  "inputs": [],
  "status": "ok",
  "output": 42
}
```

---

## Security

For **vulnerability reporting**, use this repository’s [**Security**](https://github.com/intentproof/intentproof-sdk-python/security) tab (private advisories).

Every **`ExecutionEvent`** you emit is data you may ship off-process. Treat them like audit-grade execution records: they can include PII, secrets, stack traces, and business identifiers depending on your **`snapshot`** / **`capture_*`** hooks.

- **Minimize payload:** Use **`redact_keys`**, **`max_depth`** / **`max_keys`** / **`max_string_length`**, and narrow **`capture_input`** / **`capture_output`** / **`capture_error`** so proof records contain only what verifiers need.
- **Stacks:** Set **`include_error_stack: False`** on the client (or per wrap) when traces must not leave your trust zone.
- **HTTP ingest:** Keep collector **`url`** and any redirect behavior under **trusted configuration** (avoid SSRF if URLs were ever influenced by untrusted input). Prefer **HTTPS** and **short-lived credentials** end-to-end.
- **`HttpExporter` auth:** Pass credentials in **`headers`** (for example **`Authorization: Bearer …`**, **`x-api-key`**, or whatever your collector expects). The SDK does **not** log header values; use short-lived tokens and scope them to ingest only.
- **Runtime surface:** This package targets **CPython**; treat the ingest endpoint and headers with the same care you would for any outbound credential (including sandboxed or embedded runtimes).
- **Delivery semantics:** Exporter failures invoke **`on_exporter_error`** and do **not** roll back the wrapped callable’s side effects—design compensating controls if you need strict “delivered exactly once” guarantees.

Custom **`body`** serializers: if **`body(event)`** raises, **`HttpExporter`** notifies **`on_error`** and falls back to the same **JSON envelope** path as the default serializer (full event, then a partial envelope, then a minimal `eventSerializeFailed` payload) so **`export()`** still completes and the configured HTTP client runs when possible.

---

## Canonical specification (`intentproof-spec`)

Schemas, golden oracles, and the **Vitest conformance oracle** live in the **[IntentProof specification repository (`intentproof-spec`)](https://github.com/intentproof/intentproof-spec)**.

- **CI:** every push/PR runs `scripts/run-conformance.sh` from that repo (see `.github/workflows/ci.yml`).
- **Local:** clone `intentproof-spec` **next to** this repository (`../intentproof-spec`), then:

  ```bash
  tox -e spec
  ```

  Or set `INTENTPROOF_SPEC_ROOT` and run `bash scripts/spec-conformance.sh`.

---

## Project development

Layout: **`src/`** tree, built with **Hatchling** ([Hatch](https://github.com/pypa/hatch); **`build-backend = "hatchling.build"`** in `pyproject.toml`). Requires **Python** 3.11 or newer. Release history: [`CHANGELOG.md`](CHANGELOG.md).

Checks run via **[tox](https://tox.wiki/)** (`tox.ini`): **`static`** runs **ruff** (format + lint); **`cov`** runs **pytest** with **pytest-cov** and enforces **100%** line coverage; **`py311`** … **`py314`** install the package with **`dev`** extras and run **pytest**. CI matches this.

```bash
pip install "tox>=4"          # or: pipx install tox
tox run -e static             # ruff only (matches CI static job)
tox run -e cov                # pytest + 100% coverage gate (matches CI cov job)
tox run -e audit              # CVE scan (pip-audit; dev/build toolchain)
tox run -e ALL                # static + every Python on PATH (missing interpreters skipped)
python -m build               # optional wheel/sdist — uses dev extra: pip install -e ".[dev]"
```

**Supply chain:** Runtime **`dependencies`** are empty; **`pip-audit`** checks **dev** tooling (and future runtime deps). Run **`pip-audit`** after **`pip install -e ".[dev]"`**, or **`tox run -e audit`**. On **GitHub**, **Dependabot** (`.github/dependabot.yml`) proposes weekly updates for **`pyproject.toml`** and **GitHub Actions**.

For editor/tooling against an editable install (optional): **`pip install -e ".[dev]"`** in whatever environment your IDE uses.

## License

Apache-2.0 (see `LICENSE` at the repository root and in the published **PyPI** package when released).
