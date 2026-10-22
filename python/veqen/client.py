"""Recording calls: tags, budgets, the local ledger and the background sender.

Nothing here runs in your request path except an in-memory budget check and a queue append.
Events are sent in gzip batches from one daemon thread; send failures never raise into your code.
"""

from __future__ import annotations

import atexit
import contextvars
import gzip
import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone

from veqen.pricing import Usage, price_book

log = logging.getLogger("veqen")
TAG_KEYS = ("customer", "feature", "user", "project", "environment")
_tags: contextvars.ContextVar[dict | None] = contextvars.ContextVar("veqen_tags", default=None)


class BudgetExceeded(Exception):
    """Raised before a call when a budget in "block" mode is used up."""

    def __init__(self, scope: str, value: str, limit_usd: float) -> None:
        super().__init__(f"Veqen budget exceeded for {scope}={value} (limit ${limit_usd:,.2f})")
        self.scope, self.value, self.limit_usd = scope, value, limit_usd


@dataclass
class _Budget:
    scope: str
    value: str
    limit_usd: float
    period: str
    mode: str
    spent: dict = field(default_factory=dict)  # (value, period_key) -> usd

    def period_key(self, now: datetime) -> str:
        return now.strftime("%Y-%m-%d" if self.period == "day" else "%Y-%m")

    def applies(self, tags: dict) -> str | None:
        if self.scope == "org":
            return "*"
        value = tags.get(self.scope)
        return value if value is not None and self.value in ("*", value) else None


class _Client:
    def __init__(self) -> None:
        self.api_key = ""
        self.endpoint = "https://veqen-app.com"
        self.environment: str | None = None
        self.ledger_file: str | None = None
        self.flush_interval = 2.0
        self.budget_poll = 30.0
        self.queue: deque[dict] = deque(maxlen=50_000)
        self.dropped = 0
        self.budgets: list[_Budget] = []
        self.blocked: dict[tuple[str, str], float] = {}
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._idle = threading.Event()
        self._thread: threading.Thread | None = None
        self._configured = False

    def configure(self, **options) -> None:
        env = os.environ
        self.api_key = options.get("api_key") or env.get("VEQEN_API_KEY", "")
        self.endpoint = (options.get("endpoint") or env.get("VEQEN_ENDPOINT") or self.endpoint).rstrip("/")
        self.environment = options.get("environment") or env.get("VEQEN_ENVIRONMENT") or None
        self.ledger_file = options.get("ledger_file") or env.get("VEQEN_LEDGER_FILE") or None
        if self.ledger_file:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(self.ledger_file)), exist_ok=True)
            except OSError as exc:  # a read-only filesystem must not break the caller's requests
                log.warning("Can't create the Veqen ledger folder: %s", exc)
        self.flush_interval = float(options.get("flush_interval", self.flush_interval))
        self.budget_poll = float(options.get("budget_poll", self.budget_poll))
        self._configured = True
        if self.api_key and self._thread is None:
            self._thread = threading.Thread(target=self._run, name="veqen-sender", daemon=True)
            self._thread.start()
            atexit.register(self.flush, 2.0)

    def ensure(self) -> None:
        if not self._configured:
            self.configure()

    # --- budgets ---------------------------------------------------------------------------------

    def check(self, tags: dict) -> None:
        now = datetime.now(timezone.utc)
        for (scope, value), limit in self.blocked.items():
            if scope == "org" or tags.get(scope) == value:
                raise BudgetExceeded(scope, value, limit)
        for budget in self.budgets:
            value = budget.applies(tags)
            spent = budget.spent.get((value, budget.period_key(now)), 0.0) if value else 0.0
            if value and budget.mode == "block" and spent >= budget.limit_usd:
                raise BudgetExceeded(budget.scope, value, budget.limit_usd)

    def _spend(self, tags: dict, usd: float) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            for budget in self.budgets:
                value = budget.applies(tags)
                if value:
                    key = (value, budget.period_key(now))
                    before = budget.spent.get(key, 0.0)
                    budget.spent[key] = before + usd
                    if budget.mode == "warn" and before < budget.limit_usd <= before + usd:
                        log.warning("Veqen budget reached for %s=%s: $%.2f of $%.2f this %s",
                                    budget.scope, value, before + usd, budget.limit_usd, budget.period)

    # --- recording -------------------------------------------------------------------------------

    def record(
        self,
        provider: str | None,
        model: str,
        usage: Usage,
        *,
        tags: dict,
        batch: bool = False,
        service_tier: str | None = None,
        residency: str | None = None,
        latency_ms: int | None = None,
        status: str = "ok",
        cost_usd: float | None = None,
        variant: str | None = None,
    ) -> dict:
        self.ensure()
        book = price_book()
        price = book.lookup(model, provider)
        if price is not None:
            # A provider the book doesn't know (your own servers) stays as given, priced at list until it has a
            # custom price in the cloud ledger.
            if not provider or provider.lower() == "unknown" or book.provider_of(provider):
                provider = price.provider
            # A call that reported no usage keeps the cost it came with, rather than pricing at zero.
            if usage.tokens or usage.units or cost_usd is None:
                priced = price.cost(
                    usage, batch=batch, service_tier=service_tier, residency=residency, variant=variant,
                    multipliers=book.residency.get(price.provider),
                )
                cost_usd = priced if priced is not None else cost_usd
        environment = tags.get("environment") or self.environment
        event = {
            "id": uuid.uuid4().hex,
            "ts": datetime.now(timezone.utc).isoformat(),
            "provider": book.provider_of(provider) or (provider or "unknown").lower(),
            "model": price.model if price else model,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cache_read_tokens": usage.cache_read_tokens,
            "cache_write_tokens": usage.cache_write_tokens,
            "cache_write_1h_tokens": usage.cache_write_1h_tokens,
            "audio_input_tokens": usage.audio_input_tokens,
            "audio_output_tokens": usage.audio_output_tokens,
            "units": usage.units,
            "variant": variant,
            "batch": batch,
            "service_tier": service_tier,
            "residency": residency,
            "cost_usd": cost_usd,
            "price_version": book.version,
            **{k: tags[k] for k in TAG_KEYS if tags.get(k) is not None},
            "environment": environment,
            "tags": {k: v for k, v in tags.items() if k not in TAG_KEYS},
            "latency_ms": latency_ms,
            "status": status,
        }
        if cost_usd:
            self._spend(tags, cost_usd)
        if self.ledger_file:
            try:
                with self._lock, open(self.ledger_file, "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(event) + "\n")
            except OSError as exc:  # a full disk must not break the caller's request
                log.warning("Couldn't write the Veqen ledger file: %s", exc)
        if self.api_key:
            if len(self.queue) == self.queue.maxlen:
                self.dropped += 1
            self.queue.append(event)
            if len(self.queue) >= 500:
                self._wake.set()
        return event

    # --- sending ---------------------------------------------------------------------------------

    def _request(self, method: str, path: str, body: bytes | None = None) -> dict:
        headers = {"Authorization": f"Bearer {self.api_key}", "User-Agent": "veqen-python/1.0"}
        if body is not None:
            headers |= {"Content-Type": "application/json", "Content-Encoding": "gzip"}
        request = urllib.request.Request(self.endpoint + path, data=body, headers=headers, method=method)
        with urllib.request.urlopen(request, timeout=10) as response:  # noqa: S310 - configured endpoint
            return json.loads(response.read() or b"{}")

    def _send(self) -> None:
        while self.queue:
            batch = [self.queue[i] for i in range(min(500, len(self.queue)))]
            body = gzip.compress(json.dumps({"events": batch}).encode())
            for attempt in range(4):
                try:
                    self._request("POST", "/v1/events", body)
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code != 429 and exc.code < 500:
                        log.warning("Veqen rejected %d events (HTTP %s); dropping them", len(batch), exc.code)
                        break
                except (urllib.error.URLError, OSError, TimeoutError):
                    pass
                time.sleep(min(2**attempt, 8))
            else:
                return  # still failing: keep the events and try again on the next cycle
            for _ in batch:
                self.queue.popleft()

    def _poll_budgets(self) -> None:
        try:
            status = self._request("GET", "/v1/budgets/status")
            self.blocked = {(b["scope"], b["value"]): b["limit_usd"] for b in status.get("blocked", [])}
        except (urllib.error.URLError, OSError, TimeoutError, ValueError, KeyError):
            pass  # keep the last known state

    def _run(self) -> None:
        last_poll = 0.0
        while True:
            self._wake.wait(self.flush_interval)
            self._wake.clear()
            self._idle.clear()
            if time.monotonic() - last_poll >= self.budget_poll:
                self._poll_budgets()
                last_poll = time.monotonic()
            self._send()
            self._idle.set()

    def flush(self, timeout: float = 5.0) -> bool:
        """Send everything queued; returns True when the queue is empty. Call it before a serverless
        function returns."""
        if not self.api_key or self._thread is None:
            return True
        deadline = time.monotonic() + timeout
        while self.queue and (remaining := deadline - time.monotonic()) > 0:
            self._idle.clear()
            self._wake.set()
            self._idle.wait(remaining)
        return not self.queue


client = _Client()


def init(
    api_key: str | None = None,
    *,
    endpoint: str | None = None,
    environment: str | None = None,
    ledger_file: str | None = None,
    flush_interval: float = 2.0,
    budget_poll: float = 30.0,
) -> None:
    """Configure Veqen. Without an API key, costs are computed locally (and written to ``ledger_file``
    if set) and nothing is sent anywhere. Reads VEQEN_API_KEY, VEQEN_ENDPOINT, VEQEN_ENVIRONMENT and
    VEQEN_LEDGER_FILE when arguments are omitted."""
    client.configure(
        api_key=api_key, endpoint=endpoint, environment=environment, ledger_file=ledger_file,
        flush_interval=flush_interval, budget_poll=budget_poll,
    )


@contextmanager
def tags(**values: str | None):
    """Attribute every call inside the block: ``with veqen.tags(customer="acme", feature="chat"):``."""
    token = _tags.set({**current_tags(), **{k: str(v) for k, v in values.items() if v is not None}})
    try:
        yield
    finally:
        _tags.reset(token)


def current_tags() -> dict:
    return dict(_tags.get() or {})


def budget(
    limit_usd: float,
    *,
    customer: str | None = None,
    feature: str | None = None,
    user: str | None = None,
    project: str | None = None,
    period: str = "month",
    mode: str = "block",
) -> None:
    """A local, in-process budget. ``customer="*"`` gives every customer their own limit, ``project="*"``
    every project. Budgets set in the Veqen dashboard are shared across all your processes and enforced too."""
    named = (("customer", customer), ("feature", feature), ("user", user), ("project", project))
    scopes = [(s, v) for s, v in named if v]
    if len(scopes) > 1 or period not in ("month", "day") or mode not in ("block", "warn"):
        raise ValueError("Use one of customer/feature/user/project, period 'month' or 'day', mode 'block' or 'warn'")
    scope, value = scopes[0] if scopes else ("org", "*")
    client.budgets.append(_Budget(scope, str(value), float(limit_usd), period, mode))


def record(
    model: str,
    *,
    provider: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    cache_write_1h_tokens: int = 0,
    audio_input_tokens: int = 0,
    audio_output_tokens: int = 0,
    units: float = 0,
    variant: str | None = None,
    batch: bool = False,
    service_tier: str | None = None,
    residency: str | None = None,
    cost_usd: float | None = None,
    **tag_values: str,
) -> dict:
    """Record a call you made yourself: batch jobs, gateways, self-hosted models, unsupported clients.
    ``units`` are images for image models, seconds for video and transcription, characters for speech,
    queries for rerank and pages for OCR; ``variant`` is an image size and quality ("hd/1024x1792") or a
    video resolution ("1080p"). Pass ``cost_usd`` for models the price book doesn't know."""
    usage = Usage(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens, cache_write_1h_tokens,
                  audio_input_tokens, audio_output_tokens, units)
    return client.record(
        provider, model, usage, tags={**current_tags(), **tag_values}, batch=batch,
        service_tier=service_tier, residency=residency, cost_usd=cost_usd, variant=variant,
    )


def flush(timeout: float = 5.0) -> bool:
    return client.flush(timeout)
