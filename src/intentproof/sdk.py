from __future__ import annotations

import asyncio
import inspect
import logging
import threading
import traceback
import uuid
from collections.abc import Awaitable, Callable, Coroutine, Mapping
from datetime import UTC, datetime
from typing import Any, TypeVar, cast

from intentproof._correlation import assert_correlation_id, correlation_scope, get_correlation_id
from intentproof._time import utc_iso_ms
from intentproof.exporters import Exporter, MemoryExporter
from intentproof.snapshot import snapshot
from intentproof.types import UNDEFINED, Attributes, ExecutionEvent, IntentProofConfig
from intentproof.validation import (
    assert_attributes_record,
    assert_wrap_options_shape,
    serialize_opts_from_wrap_options,
)

_log = logging.getLogger("intentproof")

T = TypeVar("T")

_client_singleton: IntentProofClient | None = None
_client_lock = threading.Lock()


def _default_on_exporter_error(error: BaseException, event: ExecutionEvent) -> None:
    _log.error(
        "[intentproof] exporter error",
        exc_info=(type(error), error, error.__traceback__),
    )


def _assert_exporter_at_index(ex: Any, index: int) -> None:
    if ex is None or not hasattr(ex, "export") or not callable(getattr(ex, "export", None)):
        msg = f"IntentProofClient: exporters[{index}] must be an object with an export() method"
        raise TypeError(msg)


def merge_attrs(
    a: Attributes,
    b: Attributes | None,
) -> Attributes | None:
    """Merge default and per-wrap attributes.

    Returns ``None`` when the merged map would be empty for optional event fields.
    """
    if not b or len(b) == 0:
        return dict(a) if a else None
    return {**a, **b}


def _default_inputs(args: tuple[Any, ...], kwargs: dict[str, Any], sopts: Any) -> Any:
    sk = sopts.snapshot_kwargs()
    if kwargs:
        return snapshot({"args": list(args), "kwargs": kwargs}, **sk)
    return snapshot(list(args), **sk)


def _to_error_snapshot(exc: BaseException, include_stack: bool) -> dict[str, Any]:
    if isinstance(exc, Exception):
        snap: dict[str, Any] = {"name": exc.__class__.__name__, "message": str(exc)}
        if include_stack:
            snap["stack"] = "".join(traceback.format_exception(exc))
        return snap
    return {"name": "Error", "message": str(exc)}


def _maybe_schedule_awaitable(
    r: Any,
    on_err: Callable[[BaseException, ExecutionEvent], Any],
    event: ExecutionEvent,
) -> None:
    if not inspect.isawaitable(r):
        return

    async def _await_it() -> None:
        await cast(Awaitable[Any], r)

    def _thread_main() -> None:
        try:
            asyncio.run(_await_it())
        except BaseException as exc:
            try:
                on_err(exc, event)
            except BaseException:
                _log.exception("on_exporter_error failed")

    threading.Thread(target=_thread_main, name="intentproof-exporter-await", daemon=True).start()


class IntentProofClient:
    def __init__(self, config: IntentProofConfig | None = None) -> None:
        self._lock = threading.Lock()
        self._exporters: list[Exporter] = [MemoryExporter()]
        OnErr = Callable[[BaseException, ExecutionEvent], Any]
        self._on_exporter_error: OnErr = _default_on_exporter_error
        self._default_attributes: Attributes = {}
        self._include_error_stack_default = True
        if config is not None:
            self.configure(config)

    def configure(self, config: IntentProofConfig) -> None:
        with self._lock:
            if config.exporters is not UNDEFINED:
                for i, ex in enumerate(config.exporters):
                    _assert_exporter_at_index(ex, i)
                self._exporters = list(config.exporters)
            if config.on_exporter_error is not UNDEFINED:
                oee = config.on_exporter_error
                if not callable(oee):
                    msg = (
                        "IntentProofClient: on_exporter_error must be a function, "
                        f"got {type(oee).__name__}"
                    )
                    raise TypeError(msg)
                self._on_exporter_error = oee
            if config.default_attributes is not UNDEFINED:
                assert_attributes_record("default_attributes", config.default_attributes)
                self._default_attributes = dict(config.default_attributes)
            if config.include_error_stack is not UNDEFINED:
                ies = config.include_error_stack
                if not isinstance(ies, bool):
                    msg = (
                        "IntentProofClient: include_error_stack must be a boolean when provided, "
                        f"got {type(ies).__name__}"
                    )
                    raise TypeError(msg)
                self._include_error_stack_default = bool(ies)

    def get_correlation_id(self) -> str | None:
        return get_correlation_id()

    def with_correlation(self, *args: Any) -> Any:
        if len(args) == 1:
            fn = args[0]
            if not callable(fn):
                msg = (
                    "IntentProofClient: expected with_correlation(fn) "
                    "or with_correlation(correlation_id, fn)"
                )
                raise TypeError(msg)
            scope_id = str(uuid.uuid4())
        elif len(args) == 2:
            cid_raw, fn = args
            if not isinstance(cid_raw, str):
                msg = "IntentProofClient: with_correlation: correlation id must be a string"
                raise TypeError(msg)
            if not callable(fn):
                msg = (
                    "IntentProofClient: expected with_correlation(fn) "
                    "or with_correlation(correlation_id, fn)"
                )
                raise TypeError(msg)
            raw = cid_raw.strip()
            scope_id = str(uuid.uuid4()) if len(raw) == 0 else assert_correlation_id(cid_raw)
        else:
            msg = "with_correlation(fn) or with_correlation(id, fn)"
            raise TypeError(msg)

        with correlation_scope(scope_id):
            return fn()

    def wrap(self, *args: Any, **kwargs: Any) -> Any:
        if len(args) == 2 and isinstance(args[0], Mapping) and callable(args[1]):
            merged = dict(cast(Mapping[str, Any], args[0]))
            merged["fn"] = args[1]
            assert_wrap_options_shape(merged)
            return self._wrap_callable(merged)
        if kwargs.get("fn") is not None:
            merged = dict(kwargs)
            assert_wrap_options_shape(merged)
            if not callable(merged["fn"]):
                t = type(merged["fn"]).__name__
                msg = f"IntentProofClient: wrap() requires callable fn, got {t}"
                raise TypeError(msg)
            return self._wrap_callable(merged)

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            merged = dict(kwargs)
            merged["fn"] = fn
            assert_wrap_options_shape(merged)
            return self._wrap_callable(merged)

        return decorator

    def _wrap_callable(self, options: dict[str, Any]) -> Callable[..., Any]:
        intent = str(options["intent"]).strip()
        action = str(options["action"]).strip()
        fn = cast(Callable[..., Any], options["fn"])
        wrap_attrs = cast(Attributes | None, options.get("attributes"))
        correlation_kw = options.get("correlation_id")
        capture_input = options.get("capture_input")
        capture_output = options.get("capture_output")
        capture_error = options.get("capture_error")
        if "include_error_stack" in options:
            include_stack = bool(options["include_error_stack"])
        else:
            include_stack = self._include_error_stack_default
        sopts = serialize_opts_from_wrap_options(options)

        if inspect.iscoroutinefunction(fn):

            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                return await self._invoke_async(
                    fn,
                    args,
                    kwargs,
                    intent=intent,
                    action=action,
                    wrap_attrs=wrap_attrs,
                    correlation_kw=correlation_kw,
                    capture_input=capture_input,
                    capture_output=capture_output,
                    capture_error=capture_error,
                    include_stack=include_stack,
                    sopts=sopts,
                )

            return async_wrapper

        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            return self._invoke_sync(
                fn,
                args,
                kwargs,
                intent=intent,
                action=action,
                wrap_attrs=wrap_attrs,
                correlation_kw=correlation_kw,
                capture_input=capture_input,
                capture_output=capture_output,
                capture_error=capture_error,
                include_stack=include_stack,
                sopts=sopts,
            )

        return sync_wrapper

    def _resolve_correlation_id(self, correlation_kw: Any) -> str | None:
        if correlation_kw is not None:
            s = str(correlation_kw).strip()
            return s or None
        return get_correlation_id()

    def _emit_exporters(self, event: ExecutionEvent) -> None:
        for exp in self._exporters:
            try:
                r = exp.export(event)
                _maybe_schedule_awaitable(r, self._on_exporter_error, event)
            except BaseException as exc:
                try:
                    self._on_exporter_error(exc, event)
                except BaseException:
                    _log.exception("on_exporter_error failed")

    def _build_event(
        self,
        *,
        intent: str,
        action: str,
        inputs: Any,
        status: str,
        started: str,
        completed: str,
        duration_ms: int,
        correlation_id: str | None,
        wrap_attrs: Attributes | None,
        output: Any | None,
        error: dict[str, Any] | None,
    ) -> ExecutionEvent:
        attrs = merge_attrs(self._default_attributes, wrap_attrs)
        return ExecutionEvent(
            id=str(uuid.uuid4()),
            intent=intent,
            action=action,
            inputs=inputs,
            status=cast(Any, status),
            started_at=started,
            completed_at=completed,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
            output=output,
            error=error,
            attributes=attrs,
        )

    def _invoke_sync(
        self,
        fn: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        intent: str,
        action: str,
        wrap_attrs: Attributes | None,
        correlation_kw: Any,
        capture_input: Callable[..., Any] | None,
        capture_output: Callable[..., Any] | None,
        capture_error: Callable[..., Any] | None,
        include_stack: bool,
        sopts: Any,
    ) -> Any:
        t0 = datetime.now(UTC)
        started = utc_iso_ms(t0)
        correlation_id = self._resolve_correlation_id(correlation_kw)

        if capture_input is not None:
            try:
                inputs = capture_input(args)
            except BaseException:
                inputs = _default_inputs(args, kwargs, sopts)
        else:
            inputs = _default_inputs(args, kwargs, sopts)

        try:
            result = fn(*args, **kwargs)
        except BaseException as exc:
            t1 = datetime.now(UTC)
            completed = utc_iso_ms(t1)
            duration_ms = int((t1 - t0).total_seconds() * 1000)
            err = _to_error_snapshot(exc, include_stack)
            out: Any | None = None
            if capture_error is not None:
                try:
                    out = capture_error(exc)
                except BaseException:
                    out = None
            event = self._build_event(
                intent=intent,
                action=action,
                inputs=inputs,
                status="error",
                started=started,
                completed=completed,
                duration_ms=duration_ms,
                correlation_id=correlation_id,
                wrap_attrs=wrap_attrs,
                output=out,
                error=err,
            )
            self._emit_exporters(event)
            raise

        t1 = datetime.now(UTC)
        completed = utc_iso_ms(t1)
        duration_ms = int((t1 - t0).total_seconds() * 1000)
        if capture_output is not None:
            try:
                output = capture_output(result)
            except BaseException:
                output = snapshot(result, **sopts.snapshot_kwargs())
        else:
            output = snapshot(result, **sopts.snapshot_kwargs())

        event = self._build_event(
            intent=intent,
            action=action,
            inputs=inputs,
            status="ok",
            started=started,
            completed=completed,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
            wrap_attrs=wrap_attrs,
            output=output,
            error=None,
        )
        self._emit_exporters(event)
        return result

    async def _invoke_async(
        self,
        fn: Callable[..., Coroutine[Any, Any, Any]],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        *,
        intent: str,
        action: str,
        wrap_attrs: Attributes | None,
        correlation_kw: Any,
        capture_input: Callable[..., Any] | None,
        capture_output: Callable[..., Any] | None,
        capture_error: Callable[..., Any] | None,
        include_stack: bool,
        sopts: Any,
    ) -> Any:
        t0 = datetime.now(UTC)
        started = utc_iso_ms(t0)
        correlation_id = self._resolve_correlation_id(correlation_kw)

        if capture_input is not None:
            try:
                inputs = capture_input(args)
            except BaseException:
                inputs = _default_inputs(args, kwargs, sopts)
        else:
            inputs = _default_inputs(args, kwargs, sopts)

        try:
            result = await fn(*args, **kwargs)
        except BaseException as exc:
            t1 = datetime.now(UTC)
            completed = utc_iso_ms(t1)
            duration_ms = int((t1 - t0).total_seconds() * 1000)
            err = _to_error_snapshot(exc, include_stack)
            out: Any | None = None
            if capture_error is not None:
                try:
                    out = capture_error(exc)
                except BaseException:
                    out = None
            event = self._build_event(
                intent=intent,
                action=action,
                inputs=inputs,
                status="error",
                started=started,
                completed=completed,
                duration_ms=duration_ms,
                correlation_id=correlation_id,
                wrap_attrs=wrap_attrs,
                output=out,
                error=err,
            )
            self._emit_exporters(event)
            raise

        t1 = datetime.now(UTC)
        completed = utc_iso_ms(t1)
        duration_ms = int((t1 - t0).total_seconds() * 1000)
        if capture_output is not None:
            try:
                output = capture_output(result)
            except BaseException:
                output = snapshot(result, **sopts.snapshot_kwargs())
        else:
            output = snapshot(result, **sopts.snapshot_kwargs())

        event = self._build_event(
            intent=intent,
            action=action,
            inputs=inputs,
            status="ok",
            started=started,
            completed=completed,
            duration_ms=duration_ms,
            correlation_id=correlation_id,
            wrap_attrs=wrap_attrs,
            output=output,
            error=None,
        )
        self._emit_exporters(event)
        return result

    async def flush(self) -> None:
        async def one(exp: Exporter) -> None:
            fl = getattr(exp, "flush", None)
            if fl is None:
                return
            r = fl()
            if inspect.isawaitable(r):
                await cast(Awaitable[Any], r)

        await asyncio.gather(*[one(e) for e in self._exporters])

    async def shutdown(self) -> None:
        async def one(exp: Exporter) -> None:
            sd = getattr(exp, "shutdown", None)
            if sd is not None:
                r = sd()
                if inspect.isawaitable(r):
                    await cast(Awaitable[Any], r)
                return
            fl = getattr(exp, "flush", None)
            if fl is not None:
                r = fl()
                if inspect.isawaitable(r):
                    await cast(Awaitable[Any], r)

        await asyncio.gather(*[one(e) for e in self._exporters])


def create_intent_proof_client(config: IntentProofConfig | None = None) -> IntentProofClient:
    return IntentProofClient(config)


def get_intent_proof_client() -> IntentProofClient:
    global _client_singleton
    with _client_lock:
        if _client_singleton is None:
            _client_singleton = IntentProofClient()
        return _client_singleton


class _DefaultClientProxy:
    __slots__ = ()

    def __getattr__(self, name: str) -> Any:
        return getattr(get_intent_proof_client(), name)


client = _DefaultClientProxy()
