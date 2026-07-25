"""TLS for the Supabase Postgres connection.

Supabase's connection pooler presents a certificate issued by *Supabase Root
2021 CA*, a private CA that is not in any public trust store. So
`ssl.create_default_context()` correctly rejects it:

    [SSL: CERTIFICATE_VERIFY_FAILED] self-signed certificate in certificate chain

which is why booking persistence was silently down. The fix is to trust that one
published root — verification stays fully on, including hostname checking. The
alternative fix seen elsewhere in this codebase (let asyncpg negotiate from the
URL's sslmode, which encrypts without verifying) leaves the connection open to
interception.

Root CA: certs/supabase-prod-ca-2021.pem, valid 2021-04-28 to 2031-04-26.
Download: https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt
"""
from __future__ import annotations

import logging
import os
import ssl
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SUPABASE_CA_PATH = Path(
    os.getenv(
        "SUPABASE_CA_CERT_PATH",
        str(Path(__file__).resolve().parent / "certs" / "supabase-prod-ca-2021.pem"),
    )
)


def supabase_ssl_context() -> Optional[ssl.SSLContext]:
    """A verifying SSL context that trusts Supabase's published root CA.

    Returns None when TLS is explicitly disabled for local Postgres. Falls back
    to the system trust store if the pinned CA is missing, which fails loudly at
    connect time rather than quietly downgrading to an unverified connection.
    """
    if os.getenv("SUPABASE_DB_DISABLE_SSL", "false").lower() == "true":
        return None

    if not SUPABASE_CA_PATH.exists():
        logger.warning(
            "[DB] Supabase CA not found at %s — falling back to the system trust "
            "store, which does not include Supabase's private root.",
            SUPABASE_CA_PATH,
        )
        return ssl.create_default_context()

    return ssl.create_default_context(cafile=str(SUPABASE_CA_PATH))
