from __future__ import annotations

import ssl

from macaronys_backend.database import build_async_engine_options


def test_build_async_engine_options_normalizes_hosted_postgres_url() -> None:
    options = build_async_engine_options(
        "postgresql://user:password@example.com/neondb?sslmode=require"
    )

    assert options["url"] == "postgresql+asyncpg://user:password@example.com/neondb"
    ssl_context = options["connect_args"]["ssl"]
    assert isinstance(ssl_context, ssl.SSLContext)
    assert ssl_context.verify_mode == ssl.CERT_NONE


def test_build_async_engine_options_keeps_asyncpg_local_url() -> None:
    options = build_async_engine_options(
        "postgresql+asyncpg://user:password@localhost:55432/app"
    )

    assert options["url"] == "postgresql+asyncpg://user:password@localhost:55432/app"
    assert options["connect_args"] == {}
