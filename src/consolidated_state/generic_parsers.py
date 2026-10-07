from __future__ import annotations

import difflib
import re
from datetime import date, datetime
from decimal import Decimal

from .layout import DocumentLayout, LayoutRow, LayoutWord
from .models import ParseResult, StatementSummary, Transaction


class GenericParseError(ValueError):
    pass


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def parse_date(value: str) -> date | None:
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%m/%d/%y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
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
                    and not any(parse_date(word.text) for word in row.words)
                    and len(row.words) <= 8
                ):
                    has_section = True

        return has_date_amount_header and has_section

    def parse(self, layout: DocumentLayout, source_file: str) -> ParseResult:
        transactions: list[Transaction] = []
        direction: str | None = None
        current: Transaction | None = None

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
                contains_date = any(parse_date(word.text) for word in row.words)

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
                    if parse_date(word.text) is not None
                ]

                if date_words and direction:
                    if current is not None:
                        transactions.append(current)

                    date_word = min(date_words, key=lambda word: word.x0)
                    transaction_date = parse_date(date_word.text)
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
                    if normalized_line.startswith(("continued", "page")):
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


class LedgerColumnsStrategy:
    """Handles running ledgers with Date / Debit / Credit / Balance columns."""

    name = "ledger-date-debit-credit-balance-v1"

    @staticmethod
    def header(row: LayoutRow) -> bool:
        words = {normalize(word.text) for word in row.words}
        return {"date", "debit", "credit", "balance"}.issubset(words)

    def matches(self, layout: DocumentLayout) -> bool:
        return any(
            self.header(row)
            for page in layout.pages
            for row in page.rows
        )

    def parse(self, layout: DocumentLayout, source_file: str) -> ParseResult:
        transactions: list[Transaction] = []

        for page in layout.pages:
            header_index = None
            header = None

            for index, row in enumerate(page.rows):
                if self.header(row):
                    header_index = index
                    header = row
                    break

            if header is None or header_index is None:
                continue

            centers: dict[str, float] = {}
            for key in ("debit", "credit", "balance"):
                word = next(
                    word for word in header.words
                    if normalize(word.text) == key
                )
                centers[key] = word.center_x

            detail_words = [
                word
                for word in header.words
                if normalize(word.text)
                in {"transaction", "details", "description", "narrative"}
            ]
            detail_x = min(
                (word.x0 for word in detail_words),
                default=page.width * 0.20,
            )

            debit_center = centers["debit"]
            credit_center = centers["credit"]
            balance_center = centers["balance"]

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
                    if parse_date(word.text) is not None and word.x0 < detail_x
                ]

                if date_words:
                    if current is not None:
                        transactions.append(current)

                    date_word = min(date_words, key=lambda word: word.x0)
                    transaction_date = parse_date(date_word.text)
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
                "A ledger layout was detected, but no transaction rows could be extracted."
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
