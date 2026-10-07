from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime

from .layout import DocumentLayout


@dataclass(frozen=True)
class StatementMetadata:
    statement_start: date | None = None
    statement_end: date | None = None
    account_fingerprint: str | None = None
    currency: str | None = None


ISO_CURRENCIES = {
    "USD", "EUR", "GBP", "PKR", "INR", "CAD", "AUD", "AED", "SAR", "JPY",
    "CNY", "CHF", "NZD", "SGD", "HKD", "BDT", "LKR", "TRY", "MXN", "BRL",
    "ZAR", "SEK", "NOK", "DKK", "PLN", "CZK", "HUF", "ILS", "QAR", "KWD",
    "BHD", "OMR", "MYR", "IDR", "THB", "PHP", "KRW", "VND",
}


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _parse_token_date(value: str) -> date | None:
    for fmt in ("%d-%b-%y", "%d-%b-%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_long_date(value: str) -> date | None:
    cleaned = re.sub(r"\s+", " ", value.strip())
    for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _find_statement_period(layout: DocumentLayout) -> tuple[date | None, date | None]:
    long_date = re.compile(
        r"\b([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})\s+to\s+"
        r"([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})\b",
        re.IGNORECASE,
    )

    for page in layout.pages:
        for row in page.rows:
            token_dates = [
                parsed
                for word in row.words
                if (parsed := _parse_token_date(word.text)) is not None
            ]
            normalized = _normalize(row.text)

            if len(token_dates) >= 2 and (
                "statementperiod" in normalized
                or ("fromdate" in normalized and "todate" in normalized)
            ):
                return token_dates[0], token_dates[1]

            match = long_date.search(row.text)
            if match:
                start = _parse_long_date(match.group(1))
                end = _parse_long_date(match.group(2))
                if start and end:
                    return start, end

    return None, None


def _find_account_fingerprint(layout: DocumentLayout) -> str | None:
    label = re.compile(
        r"(?:account\s*(?:number|no\.?|#)|acct\s*(?:number|no\.?|#))"
        r"\s*[:#]?\s*([A-Za-z0-9Xx*• ]{4,40})",
        re.IGNORECASE,
    )

    for page in layout.pages[:3]:
        for row in page.rows:
            match = label.search(row.text)
            if not match:
                continue

            candidate = re.sub(r"[^A-Za-z0-9Xx*•]", "", match.group(1))
            if len(candidate) < 4:
                continue

            digest = hashlib.sha256(
                f"account::{candidate.upper()}".encode("utf-8")
            ).hexdigest()
            return digest[:20]

    return None


def _find_currency(layout: DocumentLayout) -> str | None:
    for page in layout.pages[:3]:
        for row in page.rows:
            normalized = _normalize(row.text)
            if "currency" not in normalized and "ccy" not in normalized:
                continue

            candidates = [
                word.text.upper().strip(":/,")
                for word in row.words
                if word.text.upper().strip(":/,") in ISO_CURRENCIES
            ]
            if candidates:
                return candidates[-1]

    return None


def extract_statement_metadata(layout: DocumentLayout) -> StatementMetadata:
    start, end = _find_statement_period(layout)
    return StatementMetadata(
        statement_start=start,
        statement_end=end,
        account_fingerprint=_find_account_fingerprint(layout),
        currency=_find_currency(layout),
    )
