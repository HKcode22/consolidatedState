from __future__ import annotations

import difflib
import re
from datetime import date, datetime
from decimal import Decimal

from .layout import DocumentLayout, LayoutRow, LayoutWord
from .metadata import extract_statement_metadata
from .models import ParseResult, StatementSummary, Transaction


class GenericParseError(ValueError):
    pass


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


NUMERIC_DATE = re.compile(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})$")


def _looks_like_date_token(value: str) -> bool:
    if NUMERIC_DATE.fullmatch(value.strip()):
        return True

    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue

    return False


def parse_date(
    value: str,
    numeric_order: str | None = None,
) -> date | None:
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    match = NUMERIC_DATE.fullmatch(value.strip())
    if not match:
        return None

    first, second, year_text = match.groups()
    first_number = int(first)
    second_number = int(second)
    year_number = int(year_text)
    if year_number < 100:
        year_number += 2000

    if first_number > 12 and second_number <= 12:
        order = "DMY"
    elif second_number > 12 and first_number <= 12:
        order = "MDY"
    else:
        order = numeric_order

    if order not in {"MDY", "DMY"}:
        return None

    month = first_number if order == "MDY" else second_number
    day = second_number if order == "MDY" else first_number

    try:
        return date(year_number, month, day)
    except ValueError:
        return None


def infer_numeric_date_order(layout: DocumentLayout) -> str | None:
    evidence: set[str] = set()
    ambiguous_tokens: list[str] = []

    for page in layout.pages:
        for row in page.rows:
            for word in row.words:
                match = NUMERIC_DATE.fullmatch(word.text.strip())
                if not match:
                    continue

                first_number = int(match.group(1))
                second_number = int(match.group(2))

                if first_number > 12 and second_number <= 12:
                    evidence.add("DMY")
                elif second_number > 12 and first_number <= 12:
                    evidence.add("MDY")
                elif first_number <= 12 and second_number <= 12:
                    ambiguous_tokens.append(word.text.strip())

    if len(evidence) > 1:
        raise GenericParseError(
            "Conflicting numeric date conventions were detected in the same statement."
        )

    if len(evidence) == 1:
        return next(iter(evidence))

    metadata = extract_statement_metadata(layout)
    if (
        metadata.statement_start is None
        or metadata.statement_end is None
        or not ambiguous_tokens
    ):
        return None

    period_start = metadata.statement_start
    period_end = metadata.statement_end
    period_evidence: set[str] = set()

    for token in ambiguous_tokens:
        mdy = parse_date(token, "MDY")
        dmy = parse_date(token, "DMY")

        mdy_inside = (
            mdy is not None
            and period_start <= mdy <= period_end
        )
        dmy_inside = (
            dmy is not None
            and period_start <= dmy <= period_end
        )

        if mdy_inside and not dmy_inside:
            period_evidence.add("MDY")
        elif dmy_inside and not mdy_inside:
            period_evidence.add("DMY")

    if len(period_evidence) == 1:
        return next(iter(period_evidence))

    return None


def money_from_words(words: list[LayoutWord]) -> Decimal | None:
    if not words:
        return None

    raw = "".join(word.text for word in words)
    cleaned = re.sub(r"[^0-9.]", "", raw.replace(",", ""))

    if not re.fullmatch(r"\d+\.\d{2}", cleaned):
        return None

    try:
        return Decimal(cleaned)
    except Exception:
        return None


def rightmost_money_cluster(words: list[LayoutWord]) -> Decimal | None:
    ordered = sorted(words, key=lambda word: word.x0)
    end_index = None

    for index in range(len(ordered) - 1, -1, -1):
        if re.search(r"\d[\d,]*\.\d{2}\D*$", ordered[index].text):
            end_index = index
            break

    if end_index is None:
        return None

    selected = [ordered[end_index]]
    index = end_index - 1

    while index >= 0:
        previous = ordered[index]
        gap = selected[0].x0 - previous.x1
        numeric_fragment = re.sub(r"[^0-9]", "", previous.text)

        if gap <= 6 and numeric_fragment and len(numeric_fragment) <= 3:
            selected.insert(0, previous)
            index -= 1
        else:
            break

    return money_from_words(selected)


def find_labeled_balance(layout: DocumentLayout, phrases: tuple[str, ...]) -> Decimal | None:
    for page in layout.pages:
        for row in page.rows:
            normalized = normalize(row.text)
            if not any(phrase in normalized for phrase in phrases):
                continue

            candidates: list[LayoutWord] = []
            for nearby in page.rows:
                if abs(nearby.y - row.y) <= 6:
                    candidates.extend(
                        word for word in nearby.words
                        if word.x0 >= page.width * 0.45
                    )

            value = rightmost_money_cluster(candidates)
            if value is not None:
                return value

    return None


def statement_period(transactions: list[Transaction]) -> str:
    if not transactions:
        return ""

    dates = [transaction.date for transaction in transactions]
    return f"{min(dates).isoformat()} to {max(dates).isoformat()}"


def section_direction(line: str) -> str | None:
    tokens = [normalize(token) for token in re.findall(r"\S+", line)]

    positive_prefixes = ("deposit", "addition", "credit", "income", "receipt")
    negative_prefixes = ("withdraw", "subtract", "debit", "payment", "expense")

    if any(any(token.startswith(prefix) for prefix in positive_prefixes) for token in tokens):
        return "credit"

    if any(any(token.startswith(prefix) for prefix in negative_prefixes) for token in tokens):
        return "debit"

    for token in tokens:
        if len(token) < 5:
            continue

        if any(
            difflib.SequenceMatcher(None, token, keyword).ratio() >= 0.80
            for keyword in ("withdrawals", "subtractions", "debits", "payments")
        ):
            return "debit"

        if any(
            difflib.SequenceMatcher(None, token, keyword).ratio() >= 0.84
            for keyword in ("deposits", "additions", "credits")
        ):
            return "credit"

    return None


class SectionedAmountStrategy:
    """Handles statement layouts that split money-in and money-out into sections."""

    name = "sectioned-date-description-amount-v1"

    def matches(self, layout: DocumentLayout) -> bool:
        has_date_amount_header = False
        has_section = False

        for page in layout.pages:
            for row in page.rows:
                normalized_words = {normalize(word.text) for word in row.words}

                if "date" in normalized_words and "amount" in normalized_words:
                    has_date_amount_header = True

                if (
                    section_direction(row.text) is not None
                    and not any(_looks_like_date_token(word.text) for word in row.words)
                    and len(row.words) <= 8
                ):
                    has_section = True

        return has_date_amount_header and has_section

    def parse(self, layout: DocumentLayout, source_file: str) -> ParseResult:
        transactions: list[Transaction] = []
        direction: str | None = None
        current: Transaction | None = None
        date_order = infer_numeric_date_order(layout)

        for page in layout.pages:
            description_x = page.width * 0.15
            amount_center = page.width * 0.90

            for row in page.rows:
                normalized_line = normalize(row.text)

                if normalized_line.startswith("total"):
                    if current is not None:
                        transactions.append(current)
                        current = None
                    continue

                possible_direction = section_direction(row.text)
                contains_date = any(_looks_like_date_token(word.text) for word in row.words)

                if possible_direction and not contains_date and len(row.words) <= 8:
                    if current is not None:
                        transactions.append(current)
                        current = None
                    direction = possible_direction
                    continue

                normalized_words = [normalize(word.text) for word in row.words]

                if "date" in normalized_words and "amount" in normalized_words:
                    amount_word = next(
                        word for word in row.words
                        if normalize(word.text) == "amount"
                    )
                    amount_center = amount_word.center_x

                    description_candidates = [
                        word
                        for word in row.words
                        if difflib.SequenceMatcher(
                            None,
                            normalize(word.text),
                            "description",
                        ).ratio() >= 0.60
                    ]

                    if description_candidates:
                        description_x = description_candidates[0].x0
                    continue

                date_words = [
                    word for word in row.words
                    if parse_date(word.text, date_order) is not None
                ]

                if date_words and direction:
                    if current is not None:
                        transactions.append(current)

                    date_word = min(date_words, key=lambda word: word.x0)
                    transaction_date = parse_date(date_word.text, date_order)
                    assert transaction_date is not None

                    amount_words = [
                        word for word in row.words
                        if word.center_x >= amount_center - 20
                    ]
                    amount = money_from_words(amount_words)

                    if amount is None:
                        current = None
                        continue

                    description = " ".join(
                        word.text
                        for word in row.words
                        if description_x <= word.x0 < amount_center - 30
                    ).strip()

                    if direction == "credit":
                        current = Transaction(
                            transaction_date,
                            description,
                            credit=abs(amount),
                            source_file=source_file,
                        )
                    else:
                        current = Transaction(
                            transaction_date,
                            description,
                            debit=abs(amount),
                            source_file=source_file,
                        )
                    continue

                if current is not None:
                    if normalized_line.startswith("continued"):
                        transactions.append(current)
                        current = None
                        continue

                    if normalized_line.startswith("page"):
                        continue

                    continuation = " ".join(
                        word.text
                        for word in row.words
                        if description_x <= word.x0 < amount_center - 30
                    ).strip()

                    if continuation:
                        current = Transaction(
                            current.date,
                            f"{current.description} {continuation}".strip(),
                            debit=current.debit,
                            credit=current.credit,
                            balance=current.balance,
                            source_file=current.source_file,
                            statement_period=current.statement_period,
                        )

            if current is not None:
                transactions.append(current)
                current = None

        if not transactions:
            raise GenericParseError(
                "A sectioned transaction layout was detected, but no rows could be extracted."
            )

        period = statement_period(transactions)
        opening = find_labeled_balance(
            layout,
            ("beginningbalance", "openingbalance"),
        )
        closing = find_labeled_balance(
            layout,
            ("endingbalance", "closingbalance", "closingledgerbalance"),
        )

        transactions = [
            Transaction(
                transaction.date,
                transaction.description,
                debit=transaction.debit,
                credit=transaction.credit,
                balance=transaction.balance,
                source_file=transaction.source_file,
                statement_period=period,
            )
            for transaction in transactions
        ]

        return ParseResult(
            transactions,
            StatementSummary(source_file, period, opening, closing),
            self.name,
        )


DATE_HEADERS = {
    "date", "transactiondate", "trandate", "postingdate", "posteddate", "valuedate",
}
DEBIT_HEADERS = {
    "debit", "debits", "withdrawal", "withdrawals", "moneyout", "outflow", "paidout",
}
CREDIT_HEADERS = {
    "credit", "credits", "deposit", "deposits", "moneyin", "inflow", "additions",
}
BALANCE_HEADERS = {
    "balance", "runningbalance", "availablebalance",
}
AMOUNT_HEADERS = {
    "amount", "transactionamount", "activityamount",
}
DESCRIPTION_HEADERS = {
    "description", "details", "transactiondetails", "narrative", "merchant", "payee",
    "activity", "memo",
}


def _header_alias_matches(
    phrase: str,
    alias: str,
) -> bool:
    """Match header concepts conservatively, including minor PDF text clipping.

    Some PDFs visually show a complete heading while their embedded text drops
    the last character (for example "Balance" may extract as "Balanc"). Exact
    matching remains preferred; a very high-similarity fallback is used only
    for reasonably long header tokens.
    """
    if phrase == alias:
        return True

    if len(phrase) < 5 or len(alias) < 5:
        return False

    if phrase.startswith(alias) or alias.startswith(phrase):
        shorter = min(len(phrase), len(alias))
        longer = max(len(phrase), len(alias))
        return shorter / longer >= 0.88

    return difflib.SequenceMatcher(None, phrase, alias).ratio() >= 0.92


def _concept_span(
    row: LayoutRow,
    aliases: set[str],
) -> tuple[float, float] | None:
    words = list(row.words)

    for width in (3, 2, 1):
        for index in range(0, len(words) - width + 1):
            group = words[index:index + width]
            phrase = normalize(" ".join(word.text for word in group))

            if any(
                _header_alias_matches(phrase, alias)
                for alias in aliases
            ):
                left = group[0].x0
                center = (group[0].x0 + group[-1].x1) / 2
                return left, center

    return None


def _ledger_header_columns(row: LayoutRow) -> dict[str, tuple[float, float]] | None:
    concepts = {
        "date": _concept_span(row, DATE_HEADERS),
        "debit": _concept_span(row, DEBIT_HEADERS),
        "credit": _concept_span(row, CREDIT_HEADERS),
        "balance": _concept_span(row, BALANCE_HEADERS),
    }

    if any(value is None for value in concepts.values()):
        return None

    return {
        key: value
        for key, value in concepts.items()
        if value is not None
    }


def _signed_money_from_words(
    words: list[LayoutWord],
) -> tuple[Decimal | None, str | None]:
    amount = money_from_words(words)
    if amount is None:
        return None, None

    raw = " ".join(word.text for word in words).upper().strip()
    compact = raw.replace(" ", "")

    if compact.startswith("-") or (
        compact.startswith("(") and compact.endswith(")")
    ):
        return amount, "debit"

    if compact.startswith("+"):
        return amount, "credit"

    if re.search(r"\bDR\b", raw):
        return amount, "debit"

    if re.search(r"\bCR\b", raw):
        return amount, "credit"

    return amount, None


class SignedAmountBalanceStrategy:
    """Handles Date / Description / Amount / Balance ledgers.

    Direction must be explicit or provable from running-balance movement.
    Ambiguous rows are rejected.
    """

    name = "ledger-signed-amount-balance-v1"

    @staticmethod
    def header_columns(
        row: LayoutRow,
    ) -> dict[str, tuple[float, float]] | None:
        concepts = {
            "date": _concept_span(row, DATE_HEADERS),
            "amount": _concept_span(row, AMOUNT_HEADERS),
            "balance": _concept_span(row, BALANCE_HEADERS),
        }

        if any(value is None for value in concepts.values()):
            return None

        if (
            _concept_span(row, DEBIT_HEADERS) is not None
            or _concept_span(row, CREDIT_HEADERS) is not None
        ):
            return None

        return {
            key: value
            for key, value in concepts.items()
            if value is not None
        }

    def matches(self, layout: DocumentLayout) -> bool:
        return any(
            self.header_columns(row) is not None
            for page in layout.pages
            for row in page.rows
        )

    def parse(self, layout: DocumentLayout, source_file: str) -> ParseResult:
        date_order = infer_numeric_date_order(layout)
        opening = find_labeled_balance(
            layout,
            ("beginningbalance", "openingbalance"),
        )
        closing = find_labeled_balance(
            layout,
            ("endingbalance", "closingbalance", "closingledgerbalance"),
        )

        transactions: list[Transaction] = []
        previous_balance = opening

        for page in layout.pages:
            header_index = None
            header = None
            columns = None

            for index, row in enumerate(page.rows):
                detected = self.header_columns(row)
                if detected is not None:
                    header_index = index
                    header = row
                    columns = detected
                    break

            if header is None or header_index is None or columns is None:
                continue

            amount_center = columns["amount"][1]
            balance_center = columns["balance"][1]
            amount_balance_boundary = (amount_center + balance_center) / 2
            amount_left = amount_center - max(page.width * 0.10, 45)

            description_span = _concept_span(header, DESCRIPTION_HEADERS)
            detail_x = (
                description_span[0]
                if description_span is not None
                else page.width * 0.20
            )

            for row in page.rows[header_index + 1:]:
                normalized_line = normalize(row.text)
                if normalized_line.startswith(
                    ("total", "closing", "available", "note")
                ):
                    continue

                date_words = [
                    word
                    for word in row.words
                    if parse_date(word.text, date_order) is not None
                    and word.x0 < detail_x
                ]

                if not date_words:
                    if transactions:
                        continuation = " ".join(
                            word.text
                            for word in row.words
                            if detail_x - 2 <= word.x0 < amount_left
                        ).strip()

                        if continuation:
                            last = transactions[-1]
                            transactions[-1] = Transaction(
                                last.date,
                                f"{last.description} {continuation}".strip(),
                                debit=last.debit,
                                credit=last.credit,
                                balance=last.balance,
                                source_file=last.source_file,
                                statement_period=last.statement_period,
                            )
                    continue

                date_word = min(date_words, key=lambda word: word.x0)
                transaction_date = parse_date(date_word.text, date_order)
                assert transaction_date is not None

                amount_words = [
                    word for word in row.words
                    if amount_left <= word.center_x < amount_balance_boundary
                ]
                balance_words = [
                    word for word in row.words
                    if word.center_x >= amount_balance_boundary
                ]

                amount, explicit_direction = _signed_money_from_words(
                    amount_words
                )
                balance = money_from_words(balance_words)

                if amount is None or balance is None:
                    raise GenericParseError(
                        "An Amount/Balance row was missing a readable amount or balance."
                    )

                direction = explicit_direction

                if direction is None and previous_balance is not None:
                    delta = balance - previous_balance
                    if abs(abs(delta) - amount) <= Decimal("0.01"):
                        if delta > 0:
                            direction = "credit"
                        elif delta < 0:
                            direction = "debit"

                if direction is None:
                    raise GenericParseError(
                        "Debit/credit direction could not be proven for an Amount-column row."
                    )

                if previous_balance is not None:
                    expected = (
                        previous_balance + amount
                        if direction == "credit"
                        else previous_balance - amount
                    )
                    if abs(expected - balance) > Decimal("0.01"):
                        raise GenericParseError(
                            "Amount direction disagreed with the running balance."
                        )

                description = " ".join(
                    word.text
                    for word in row.words
                    if detail_x - 2 <= word.x0 < amount_left
                ).strip()

                transactions.append(
                    Transaction(
                        transaction_date,
                        description,
                        debit=amount if direction == "debit" else None,
                        credit=amount if direction == "credit" else None,
                        balance=balance,
                        source_file=source_file,
                    )
                )
                previous_balance = balance

        if not transactions:
            raise GenericParseError(
                "An Amount/Balance ledger layout was detected, but no transactions could be extracted."
            )

        if closing is None:
            closing = transactions[-1].balance

        if opening is None:
            first = transactions[0]
            if first.balance is not None:
                opening = (
                    first.balance
                    + (first.debit or Decimal("0"))
                    - (first.credit or Decimal("0"))
                )

        period = statement_period(transactions)
        transactions = [
            Transaction(
                transaction.date,
                transaction.description,
                debit=transaction.debit,
                credit=transaction.credit,
                balance=transaction.balance,
                source_file=transaction.source_file,
                statement_period=period,
            )
            for transaction in transactions
        ]

        return ParseResult(
            transactions,
            StatementSummary(source_file, period, opening, closing),
            self.name,
        )


class LedgerColumnsStrategy:
    """Handles running ledgers with two money-direction columns and a balance.

    Header wording is structural rather than bank-specific. Examples include:
    Debit/Credit, Withdrawals/Deposits, and Money Out/Money In.
    """

    name = "ledger-two-sided-columns-v2"

    @staticmethod
    def header(row: LayoutRow) -> bool:
        return _ledger_header_columns(row) is not None

    def matches(self, layout: DocumentLayout) -> bool:
        return any(
            self.header(row)
            for page in layout.pages
            for row in page.rows
        )

    def parse(self, layout: DocumentLayout, source_file: str) -> ParseResult:
        transactions: list[Transaction] = []
        date_order = infer_numeric_date_order(layout)

        for page in layout.pages:
            header_index = None
            header = None
            columns = None

            for index, row in enumerate(page.rows):
                detected = _ledger_header_columns(row)
                if detected is not None:
                    header_index = index
                    header = row
                    columns = detected
                    break

            if header is None or header_index is None or columns is None:
                continue

            debit_center = columns["debit"][1]
            credit_center = columns["credit"][1]
            balance_center = columns["balance"][1]

            description_span = _concept_span(header, DESCRIPTION_HEADERS)
            detail_x = (
                description_span[0]
                if description_span is not None
                else page.width * 0.20
            )

            debit_left = debit_center - max(page.width * 0.085, 35)
            debit_credit_boundary = (debit_center + credit_center) / 2
            credit_balance_boundary = (credit_center + balance_center) / 2

            current: Transaction | None = None

            for row in page.rows[header_index + 1:]:
                normalized_line = normalize(row.text)

                if normalized_line.startswith(
                    ("total", "closing", "available", "note")
                ):
                    if current is not None:
                        transactions.append(current)
                        current = None
                    continue

                date_words = [
                    word
                    for word in row.words
                    if parse_date(word.text, date_order) is not None and word.x0 < detail_x
                ]

                if date_words:
                    if current is not None:
                        transactions.append(current)

                    date_word = min(date_words, key=lambda word: word.x0)
                    transaction_date = parse_date(date_word.text, date_order)
                    assert transaction_date is not None

                    debit = money_from_words(
                        [
                            word for word in row.words
                            if debit_left
                            <= word.center_x
                            < debit_credit_boundary
                        ]
                    )
                    credit = money_from_words(
                        [
                            word for word in row.words
                            if debit_credit_boundary
                            <= word.center_x
                            < credit_balance_boundary
                        ]
                    )
                    balance = money_from_words(
                        [
                            word for word in row.words
                            if word.center_x >= credit_balance_boundary
                        ]
                    )

                    description = " ".join(
                        word.text
                        for word in row.words
                        if detail_x - 2 <= word.x0 < debit_left
                    ).strip()

                    current = Transaction(
                        transaction_date,
                        description,
                        debit=debit,
                        credit=credit,
                        balance=balance,
                        source_file=source_file,
                    )
                    continue

                if current is not None:
                    continuation = " ".join(
                        word.text
                        for word in row.words
                        if detail_x - 2 <= word.x0 < debit_left
                    ).strip()

                    if continuation:
                        current = Transaction(
                            current.date,
                            f"{current.description} {continuation}".strip(),
                            debit=current.debit,
                            credit=current.credit,
                            balance=current.balance,
                            source_file=current.source_file,
                            statement_period=current.statement_period,
                        )

            if current is not None:
                transactions.append(current)

        if not transactions:
            raise GenericParseError(
                "A two-sided ledger layout was detected, but no transaction rows could be extracted."
            )

        period = statement_period(transactions)
        first = transactions[0]
        last = transactions[-1]

        opening = find_labeled_balance(
            layout,
            ("beginningbalance", "openingbalance"),
        )

        if opening is None and first.balance is not None:
            opening = (
                first.balance
                + (first.debit or Decimal("0"))
                - (first.credit or Decimal("0"))
            )

        closing = find_labeled_balance(
            layout,
            ("endingbalance", "closingbalance", "closingledgerbalance"),
        )

        if closing is None:
            closing = last.balance

        transactions = [
            Transaction(
                transaction.date,
                transaction.description,
                debit=transaction.debit,
                credit=transaction.credit,
                balance=transaction.balance,
                source_file=transaction.source_file,
                statement_period=period,
            )
            for transaction in transactions
        ]

        return ParseResult(
            transactions,
            StatementSummary(source_file, period, opening, closing),
            self.name,
        )
