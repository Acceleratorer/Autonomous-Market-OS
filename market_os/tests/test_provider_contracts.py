from __future__ import annotations

import pytest

from market_os.providers import (
    CachePolicy,
    DataFreshness,
    DeterministicFixture,
    DocumentRecord,
    LicenseMetadata,
    MarketBar,
    ProviderDeadline,
    ProviderHealth,
    Provenance,
)


TIMESTAMP = "2026-01-06T00:00:00+00:00"


def test_normalized_market_bar_and_document_record_keep_source_metadata() -> None:
    provenance = Provenance("fixture", "fixture:market", TIMESTAMP, "req-1")
    bar = MarketBar(
        "SPY",
        "NYSE",
        "USD",
        TIMESTAMP,
        100.0,
        101.0,
        99.5,
        100.5,
        1000.0,
        "split_dividend",
        "fixture",
        TIMESTAMP,
        provenance,
    )
    document = DocumentRecord(
        "doc-1",
        "Policy",
        "Market OS",
        "fixture:policy",
        TIMESTAMP,
        TIMESTAMP,
        ("SPY",),
        "text/plain",
        "a" * 64,
        LicenseMetadata("fixture-only"),
        provenance,
    )
    assert bar.provenance.source_ref == "fixture:market"
    assert document.license.classification == "fixture-only"


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ProviderDeadline(0),
        lambda: ProviderHealth("fixture", "unknown", TIMESTAMP),
        lambda: DataFreshness(TIMESTAMP, "not-a-timestamp"),
        lambda: CachePolicy("unknown"),
        lambda: DeterministicFixture("", "checksum"),
    ],
)
def test_provider_contracts_reject_unsafe_metadata(factory) -> None:
    with pytest.raises(ValueError):
        factory()


def test_provider_health_accepts_utc_status() -> None:
    health = ProviderHealth("fixture", "healthy", TIMESTAMP)
    assert health.status == "healthy"
