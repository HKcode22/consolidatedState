# Understanding ConsolidatedState

This is the **read-this-first technical guide** for the project.

If you are confused about what problem we are solving, why the architecture looks the way it does, how the code flows, why we are not using an LLM, or which files matter, start here.

---

# 1. What problem are we solving?

The original request is simple to describe:

> Take multiple monthly bank statements and produce one consolidated document that combines their deposits/credits, withdrawals/debits, transaction activity, and summary totals.

For example, imagine a person has twelve monthly statements:

```text
January.pdf
February.pdf
March.pdf
...
December.pdf
```

Instead of manually copying every deposit and withdrawal into one spreadsheet, the application should:

1. accept the PDFs;
2. extract the transaction data;
3. normalize different bank layouts into one common structure;
4. verify that the extracted numbers make financial sense;
5. combine the statements;
6. show the result in the browser;
7. let the user download a consolidated Excel and PDF report.

The important phrase is **different bank layouts**.

We are not building:

```text
"If bank == Bank A, use these exact coordinates."
"If bank == Bank B, use another hardcoded parser."
```

We are trying to recognize **structural families** of statements.

That means the software asks:

> What kind of table/layout is this?

rather than:

> Which bank created this?

---

# 2. The product goal

The practical product is a small web application that a non-technical person can use.

The intended user flow is:

```text
Open website
    ↓
Upload 1–12 bank statement PDFs
    ↓
Click "Process statements"
    ↓
Application inspects and parses them
    ↓
Application validates the result
    ↓
User reviews the summary
    ↓
Download:
    - consolidated Excel workbook
    - consolidated PDF report
```

The user should **not** need:

- Python;
- GitHub;
- a terminal;
- Replit knowledge;
- an LLM;
- an API key;
- a database.

GitHub is for us as developers.

Replit is the server that runs the website.

The user's experience is only the browser.

---

# 3. Why this is not primarily an AI/LLM problem

At first, it is natural to think:

> "We are reading documents, so should we use an LLM?"

For this problem, the answer is currently **no**.

A bank statement is primarily structured financial data.

If a statement says:

```text
09/03/2026
PAYROLL
2,500.00
```

we do not want a generative model to "interpret" or rewrite 2,500.00.

We want deterministic code to extract exactly:

```text
Decimal("2500.00")
```

The system should never hallucinate a transaction.

The system should never silently change:

```text
1,842.37
```

into:

```text
1,824.37
```

The important intelligence in this project is therefore:

- document-layout recognition;
- text-coordinate analysis;
- normalization;
- validation;
- reconciliation;
- safe fallback.

An LLM could be added much later for optional tasks such as:

```text
"AMZN MKTPLACE PMTS"
        ↓
Merchant: Amazon
Category: Shopping
```

But an LLM should not be the source of truth for financial amounts.

---

# 4. High-level architecture

The application is intentionally one small Python web application.

```text
                     USER'S BROWSER
                           │
                           ▼
                      Streamlit UI
                         app.py
                           │
                           ▼
                 application pipeline
                      pipeline.py
                           │
                           ▼
                     PDF PRE-FLIGHT
                    pdf_inspect.py
                           │
              ┌────────────┴────────────┐
              │                         │
        valid text PDF?           invalid / scanned?
              │                         │
              ▼                         ▼
      coordinate extraction         block safely
          layout.py
              │
              ▼
      metadata extraction
         metadata.py
              │
              ▼
        parser registry
          parser.py
              │
      ┌───────┼────────────┐
      ▼       ▼            ▼
  strategy A strategy B strategy C
       generic_parsers.py
              │
              ▼
      normalized Transaction
           objects
          models.py
              │
              ▼
         pandas tables
        consolidate.py
              │
              ▼
       validation layer
         validate.py
              │
              ▼
      final export gate
        readiness.py
              │
        ┌─────┴─────┐
        ▼           ▼
      Excel         PDF
 export_excel.py export_pdf.py
```

This separation is very important.

Each file has one major responsibility.

That makes the system easier to test and safer to extend.

---

# 5. Frontend versus backend in this project

A common source of confusion is:

> "Where is the frontend?"

In this project, **Streamlit is the frontend framework and the application server**.

We do not currently need:

```text
React frontend
        +
FastAPI backend
        +
REST API
```

That architecture is useful for larger products, but it would add unnecessary complexity here.

Our architecture is:

```text
Browser
   ↓
Streamlit
   ↓
Python functions
   ↓
PDF parser / validation / export
```

The file:

```text
app.py
```

creates the web interface.

Examples:

```python
st.file_uploader(...)
st.button(...)
st.dataframe(...)
st.download_button(...)
```

Those Python calls render actual browser components.

So when we improve `app.py`, we are improving the frontend.

---

# 6. GitHub versus Replit

These systems have different jobs.

## GitHub

GitHub is the **source of truth for the code**.

Repository:

```text
HKcode22/consolidatedState
```

We make code changes in GitHub `main`.

Git gives us:

- version history;
- commits;
- tests;
- rollback;
- change tracking.

## Replit

Replit is the **runtime and hosting environment**.

Replit pulls the source code from GitHub and runs:

```text
streamlit run app.py
```

The important mental model is:

```text
GitHub
  │
  │ source code
  ▼
Replit
  │
  │ runs the code
  ▼
Website URL
  │
  ▼
Dad / user
```

When GitHub changes, Replit does not magically become identical unless it is synchronized.

Our normal developer workflow is:

```bash
git fetch origin
git switch main
git reset --hard origin/main
python3 -m pip install -r requirements.txt
pytest -q
```

Then Replit's configured workflow runs the Streamlit server.

---

# 7. What happens when the user uploads a PDF?

This is the most important end-to-end code path to understand.

Start in:

```text
app.py
```

The upload widget returns PDF files.

For each uploaded file:

```python
pdf_bytes = uploaded.getvalue()
```

At this point, the application has the PDF as bytes in memory.

The bytes are sent to:

```text
inspect_and_extract_pdf(...)
```

in:

```text
src/consolidated_state/pdf_inspect.py
```

That function performs the first safety checks.

---

# 8. pdf_inspect.py — PDF pre-flight

Read this file early.

Its job is **not** to understand transactions.

Its job is to answer:

```text
Is this a usable PDF?
```

It checks things such as:

- empty file;
- file size;
- invalid PDF;
- password protection;
- number of pages;
- whether embedded text exists;
- SHA-256 file hash.

Why SHA-256?

If the same PDF is uploaded twice:

```text
statement.pdf
statement-copy.pdf
```

the names are different, but the bytes are identical.

Their SHA-256 hashes will be identical.

That allows us to block exact duplicate uploads.

The result is represented by:

```text
PdfInspection
```

from `models.py`.

Possible states include:

```text
TEXT_READY
OCR_REQUIRED
PASSWORD_REQUIRED
INVALID_PDF
TOO_LARGE
```

The important principle is:

> A parser is never asked to interpret a file that failed pre-flight.

---

# 9. layout.py — preserving the visual table structure

A PDF is not the same thing as a text file.

A statement may visually look like:

```text
Date        Description          Debit      Credit      Balance
01/01       Payroll                         100.00      1,100.00
01/02       Coffee                5.00                   1,095.00
```

But plain PDF text extraction might return something closer to:

```text
Date
Description
Debit
Credit
Balance
01/01
Payroll
100.00
1,100.00
...
```

That can destroy the table relationships.

PyMuPDF can return every word with coordinates:

```text
x0
y0
x1
y1
text
```

For example:

```text
"Coffee"
x0 = 150
y0 = 100
```

and:

```text
"5.00"
x0 = 390
y0 = 100
```

Because their Y positions align, we know they belong to the same visual row.

`layout.py` converts those raw PDF words into:

```text
DocumentLayout
    ↓
PageLayout
    ↓
LayoutRow
    ↓
LayoutWord
```

This is one of the core ideas of the project.

We are not only reading text.

We are reading **text + geometry**.

---

# 10. models.py — our internal common language

Different banks describe data differently.

One might say:

```text
Withdrawal
```

another:

```text
Debit
```

another:

```text
Money Out
```

But after parsing, all of them become our internal model:

```python
Transaction(
    date=...,
    description=...,
    debit=...,
    credit=...,
    balance=...,
    source_file=...,
    statement_period=...,
)
```

This normalization is what makes consolidation possible.

Once every parser produces the same `Transaction` structure, the rest of the program does not care which bank created the PDF.

The important models are:

## Transaction

One normalized transaction.

## StatementSummary

Metadata about one source statement:

- source file;
- statement period;
- opening balance;
- closing balance;
- detected account fingerprint;
- detected currency;
- layout strategy used.

## ParseResult

The output of one parser:

```text
transactions
statement summary
parser name
```

## PdfInspection

The result of PDF pre-flight.

---

# 11. metadata.py — understanding the statement itself

The parser extracts transactions.

But a statement also contains information about the whole document.

`metadata.py` looks for things such as:

- statement start date;
- statement end date;
- account number / masked account identifier;
- explicit currency.

Example:

```text
Statement Period: 01-JAN-26 to 31-JAN-26
Currency: USD
Account ending in 4321
```

The account identifier is **not stored directly**.

Instead, the code hashes it.

Conceptually:

```text
4321
  ↓
SHA-256
  ↓
private fingerprint
```

The fingerprint lets us answer:

> Do these statements appear to belong to the same account?

without putting the actual account identifier into our generated output.

---

# 12. parser.py — the traffic controller

This file is intentionally small.

Read it before reading the large `generic_parsers.py`.

Its main job is to maintain the parser registry.

Conceptually:

```python
PARSERS = [
    LedgerColumnsStrategy(),
    SignedAmountBalanceStrategy(),
    SectionedAmountStrategy(),
]
```

Then:

```python
for parser in PARSERS:
    if parser.matches(layout):
        return parser.parse(...)
```

This is the **Strategy Pattern**.

Instead of one gigantic function containing hundreds of bank-specific conditions, we have independent structural strategies.

That means a future statement format can be added as:

```text
NewLayoutStrategy
```

without rewriting the rest of the application.

---

# 13. generic_parsers.py — the main parsing engine

This is currently the most complex file.

Do not start your code reading here.

Read the easier files first.

The parser currently recognizes three broad structural families.

---

# 14. Strategy 1 — two-sided running ledger

Examples of headers:

```text
Date | Description | Debit | Credit | Balance
```

or:

```text
Posting Date | Details | Withdrawals | Deposits | Running Balance
```

or:

```text
Date | Memo | Money Out | Money In | Balance
```

All of these mean approximately the same thing.

The code has alias groups such as:

```text
DEBIT_HEADERS
CREDIT_HEADERS
BALANCE_HEADERS
DATE_HEADERS
DESCRIPTION_HEADERS
```

The parser finds the X-position of each conceptual column.

Then for every transaction row it separates words based on those X boundaries.

Conceptually:

```text
| date area | description area | debit area | credit area | balance area |
```

This strategy is called something like:

```text
ledger-two-sided-columns-v2
```

The important idea is that the exact bank name is irrelevant.

---

# 15. Why the recent test failed

This is a useful real example of why tests matter.

The synthetic test visually created the header:

```text
Running Balance
```

very close to the right side of the PDF page.

PyMuPDF extracted:

```text
Running Balanc
```

The last letter was clipped from the embedded text representation.

Our old code required an exact alias:

```text
runningbalance
```

so:

```text
runningbalanc != runningbalance
```

and the parser refused the statement.

That caused:

```text
1 failed, 27 passed
```

This was a useful failure.

The correct fix was **not** to remove the test.

The correct fix was to make header matching tolerate very small extraction defects while remaining conservative.

The matching now:

1. prefers exact matches;
2. allows near-complete prefix matches for sufficiently long terms;
3. allows only a very high similarity score for fuzzy matching.

That means:

```text
Running Balanc
```

can match:

```text
Running Balance
```

without making arbitrary text look like financial headers.

---

# 16. Strategy 2 — sectioned statements

Some statements do not have debit and credit columns in one table.

Instead they look like:

```text
Deposits and other additions

Date       Description           Amount
...

Withdrawals and other subtractions

Date       Description           Amount
...
```

This strategy first determines which section it is currently reading:

```text
credit section
or
debit section
```

Then each amount inherits that direction.

Example:

```text
Deposits and additions
09/01 Payroll 2500.00
```

becomes:

```python
credit=Decimal("2500.00")
debit=None
```

Later:

```text
Withdrawals
09/02 Rent 1200.00
```

becomes:

```python
debit=Decimal("1200.00")
credit=None
```

This is called:

```text
sectioned-date-description-amount-v1
```

---

# 17. Strategy 3 — Amount + running Balance

Some statements contain:

```text
Date | Description | Amount | Balance
```

There is only one Amount column.

The challenge is:

> Is 100.00 money in or money out?

The program does **not** blindly guess.

It tries to prove direction using:

- `+` or `-`;
- `CR` or `DR`;
- running-balance movement.

Example:

```text
Previous balance = 1,000
Amount           = 100
New balance      = 1,100
```

The only mathematically consistent interpretation is:

```text
credit = 100
```

If:

```text
Previous = 1,100
Amount   = 5
New      = 1,095
```

then:

```text
debit = 5
```

If direction cannot be proven, the parser rejects the row.

That is safer than producing a plausible but incorrect report.

---

# 18. International date handling

Dates are surprisingly dangerous.

Consider:

```text
01/02/2026
```

In the United States that often means:

```text
January 2, 2026
```

Elsewhere it often means:

```text
1 February 2026
```

A universal statement parser should not automatically assume one.

The code therefore tries to infer the date convention.

An unambiguous date gives evidence.

Example:

```text
13/01/2026
```

cannot be MM/DD because month 13 does not exist.

Therefore:

```text
DD/MM
```

Likewise:

```text
01/31/2026
```

must be:

```text
MM/DD
```

If every transaction date is ambiguous, the parser can use the detected statement period as additional evidence.

If the program still cannot prove the convention, it refuses to guess.

---

# 19. consolidate.py — combining normalized data

After parsing, all transactions are converted into a pandas DataFrame.

Conceptually:

```text
date
description
debit
credit
balance
source_file
statement_period
```

This is where many individual statements become one common dataset.

The module also builds the monthly summary:

```text
month
total_debits
total_credits
net
```

Example:

```text
2026-08 | 18,400.00 | 24,500.00 | +6,100.00
2026-09 | 12,300.00 | 20,100.00 | +7,800.00
```

It also checks for likely transaction overlap across different source statements.

Important:

Two transactions inside the same statement are **not** automatically treated as duplicates merely because they share:

```text
same date
same description
same amount
```

That can happen legitimately.

Exact duplicate PDFs are caught separately using SHA-256.

---

# 20. Why Decimal matters

Python floating-point arithmetic can produce behavior like:

```python
0.1 + 0.2 != 0.3
```

because binary floating point cannot exactly represent many decimal fractions.

That is unacceptable for financial reconciliation.

We therefore use:

```python
Decimal("0.10")
Decimal("0.20")
```

so:

```text
0.10 + 0.20 = 0.30
```

exactly.

Look for:

```text
from decimal import Decimal
```

throughout the financial code.

---

# 21. validate.py — proving that the parse is believable

Parsing and validation are deliberately separate.

A parser saying:

> "I extracted 47 transactions."

is not enough.

The validation layer asks:

> "Does this extraction make financial sense?"

There are several checks.

## Transaction integrity

Each normalized transaction must have:

- a description;
- a source file;
- exactly one debit or credit;
- a non-negative normalized amount.

## Individual statement reconciliation

Where opening and closing balances exist:

```text
opening balance
+ total credits
- total debits
≈ closing balance
```

Example:

```text
5,000
+2,500
-1,200
-300
------
6,000
```

If the source statement says:

```text
closing balance = 6,000
```

then:

```text
PASS
```

If it says:

```text
5,950
```

then:

```text
FAIL
```

## Account consistency

If account identifiers can be detected, the system checks that the statements belong to the same account.

## Currency consistency

If explicit currencies are detected, the system blocks contradictory currencies.

The application currently does **not** convert currencies.

## Statement-period overlap

If two statements cover overlapping dates, that can cause duplicate activity.

The application flags that for review.

## Statement-period gaps

If January ends January 31 and the next statement begins February 5, there is a gap.

That is surfaced as a warning.

## Balance continuity

When consecutive statement balances are available:

```text
previous closing balance
        =
next opening balance
```

should normally hold.

---

# 22. readiness.py — the final gate

Even after all the parsing and validation work, we still do not immediately create the output.

`readiness.py` asks:

> Is it safe to export?

Blocking statuses include things such as:

```text
INVALID_PDF
PASSWORD_REQUIRED
OCR_REQUIRED
DUPLICATE_FILE
NEEDS_LAYOUT_STRATEGY
FAIL
NEEDS_REVIEW
```

If any required statement failed:

```text
EXPORT BLOCKED
```

This is called **fail-closed behavior**.

A dangerous system would do:

```text
11 statements succeeded
1 failed
→ quietly export the 11
```

Our system instead does:

```text
11 succeeded
1 failed
→ do not claim the report is complete
```

That is the correct behavior for financial data.

---

# 23. export_excel.py

This creates the detailed Excel workbook.

The workbook currently includes sheets such as:

```text
Overview
Source Statements
Credits & Deposits
Debits & Withdrawals
All Transactions
Monthly Summary
Validation
About
```

## Overview

High-level totals such as:

- covered period;
- source statement count;
- transaction count;
- deposit count;
- deposit total;
- withdrawal count;
- withdrawal total;
- net change;
- opening balance;
- ending balance.

## Source Statements

Traceability for each PDF:

- source filename;
- detected period;
- detected currency;
- whether an account identifier was detected;
- opening balance;
- closing balance;
- parser strategy used.

## Credits & Deposits

All normalized money-in transactions.

## Debits & Withdrawals

All normalized money-out transactions.

## All Transactions

Everything chronologically.

## Monthly Summary

Month-by-month totals.

## Validation

The evidence explaining whether the report passed its checks.

---

# 24. export_pdf.py

Your dad described wanting **one consolidated document**.

That is why we added PDF output in addition to Excel.

The PDF is a readable summary/report containing:

- overview;
- source statements;
- deposits/credits;
- withdrawals/debits;
- monthly summary;
- validation.

It is intentionally labeled:

> Consolidated report derived from source statements. Not an official bank-issued statement.

We are consolidating real source data.

We are not creating a fake official bank document.

---

# 25. pipeline.py — the complete application workflow

The detailed processing workflow now lives in:

```text
src/consolidated_state/pipeline.py
```

This keeps the web interface small and makes the core workflow testable without a browser.

Its logic is roughly:

```text
receive (filename, PDF bytes)
↓
inspect every PDF
↓
detect exact duplicate files
↓
run the generic parser
↓
combine normalized transactions
↓
validate transaction structure
↓
validate the set of statements
↓
reconcile every statement
↓
calculate totals
↓
run the final export gate
↓
if safe:
    generate Excel
    generate PDF
↓
return one ConsolidationResult
```

The returned `ConsolidationResult` contains the tables, totals, validation state, blocking reasons, and generated report bytes that the frontend needs.

This separation is useful because:

```text
app.py = presentation
pipeline.py = workflow
generic_parsers.py = extraction
validate.py = correctness checks
export_*.py = output
```

# 26. app.py — the browser frontend

`app.py` is now intentionally focused on the user experience.

It:

- renders the page;
- accepts PDF uploads;
- shows upload count/size;
- calls `process_statements(...)`;
- shows summary metrics;
- presents results in tabs;
- displays validation failures clearly;
- exposes the Excel/PDF download buttons;
- optionally requires a family passcode.

The important point is that `app.py` is **not** where financial parsing rules live.

That makes it safer to redesign the frontend without changing transaction extraction.

---

# 27. What the frontend looks like

The frontend should remain simple.

The user should see something like:

```text
────────────────────────────────────────
       Bank Statement Consolidator
Combine monthly bank statements safely
────────────────────────────────────────

How it works:
1. Upload
2. Process
3. Review
4. Download

[ Upload PDF statements ]

Selected:
12 files

[ Process statements ]

────────────────────────────────────────
Summary
Statements: 12
Transactions: 483
Credits: $...
Debits: $...
Validation: PASS
────────────────────────────────────────

Tabs:
[ Overview ]
[ Source Statements ]
[ Transactions ]
[ Monthly Summary ]
[ Validation ]

[ Download Excel ] [ Download PDF ]
```

The interface should not expose developer concepts unless useful.

Your dad does not need to know what:

```text
ledger-two-sided-columns-v2
```

means during normal use.

That information can appear in an advanced/source-details section for traceability.

---

# 28. Replit deployment

The local Replit preview and a published Replit app are different.

## Development preview

When Replit runs:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 5000
```

you get the workspace preview.

## Published app

Publishing creates a stable web URL intended for users.

The final experience becomes:

```text
Dad opens URL
      ↓
Streamlit app runs on Replit
      ↓
Dad uploads PDFs
      ↓
Processing occurs on the Replit server
      ↓
Dad downloads the result
```

No terminal is involved for him.

Before publication we should verify:

- tests pass;
- real sample statements work;
- no real PDFs are in GitHub;
- upload size is acceptable;
- generated files are not stored permanently;
- the privacy message is clear;
- unsupported documents fail safely.

---

# 29. .replit

This file tells Replit how to run the application.

Important part:

```text
streamlit run app.py
--server.address 0.0.0.0
--server.port 5000
```

It also maps the local Streamlit port to the web environment.

You normally do not need to edit this file.

---

# 30. .streamlit/config.toml

This contains Streamlit-specific runtime settings.

Current important settings include:

```text
headless = true
address = 0.0.0.0
port = 5000
maxUploadSize = 20
```

That means:

- run as a web server;
- listen on Replit's network interface;
- use port 5000;
- limit uploads to 20 MB per file.

---

# 31. requirements.txt

This is the dependency list.

Current major packages:

## streamlit

Web interface.

## pymupdf

PDF reading and coordinate extraction.

Imported as:

```python
import fitz
```

## pandas

Tabular data processing and summaries.

## openpyxl

Excel workbook generation.

## reportlab

PDF report generation.

## pytest

Automated testing.

When Replit runs:

```bash
python3 -m pip install -r requirements.txt
```

these libraries are installed.

---

# 32. tests/ — why these files are important

Do not think of tests as optional homework.

For this project, tests are part of the safety system.

Examples include:

- parser structure tests;
- Decimal arithmetic tests;
- duplicate detection tests;
- balance reconciliation tests;
- international date tests;
- account/currency consistency tests;
- Excel generation tests;
- PDF generation tests.

The test command is:

```bash
pytest -q
```

A good development state should look like:

```text
............................
28 passed
```

or more as the suite grows.

If even one test fails, we investigate before publishing.

---

# 33. GitHub Actions

The file:

```text
.github/workflows/tests.yml
```

runs the test suite automatically when code is pushed to `main`.

Conceptually:

```text
push code
    ↓
GitHub creates temporary Linux machine
    ↓
install Python
    ↓
install requirements
    ↓
pytest -q
    ↓
green ✓ or red ✗
```

A red GitHub check does not automatically mean the entire architecture is broken.

It means:

> At least one automated expectation failed.

We inspect the exact failing test.

That is exactly what happened with the clipped `Running Balance` header.

---

# 34. How support for more banks grows

Suppose your dad later sends another bank.

We do **not** immediately create:

```text
new_bank.py
```

First we ask:

> Does its structure match an existing generic strategy?

If yes:

```text
No parser code needed.
```

If no:

```text
Study the structural difference.
```

Maybe it looks like:

```text
Transaction Date | Value Date | Narrative | Amount | Type
```

Then we ask whether that represents a genuinely new reusable layout family.

If yes, we add:

```text
Strategy 4
```

Now every future bank using that family can potentially work.

The project becomes more universal by accumulating **layout knowledge**, not bank-name conditions.

---

# 35. What "supports any bank" realistically means

It is important to be precise.

There is no honest deterministic program that can guarantee:

> Every possible bank statement PDF on Earth will work automatically.

There are too many possibilities:

- scanned images;
- unusual fonts;
- different languages;
- image-based tables;
- encrypted PDFs;
- missing balances;
- custom business statement designs;
- malformed PDFs;
- nonstandard date formats.

Our realistic goal is:

> Broad bank-agnostic coverage with safe extensibility.

That means:

```text
Known structural family
→ parse automatically

Unknown structural family
→ refuse safely
→ study example
→ add reusable strategy
```

Over time, supported coverage increases.

---

# 36. OCR and scanned statements

Currently the pre-flight can detect a PDF that has no embedded text.

That becomes:

```text
OCR_REQUIRED
```

OCR means:

> Optical Character Recognition

Example:

```text
image of statement
        ↓
OCR
        ↓
recognized words + positions
        ↓
our parser strategies
```

OCR is different from an LLM.

A future free OCR path might use an open-source engine.

Even with OCR, the financial validation layer remains the same.

That is valuable because OCR can make mistakes.

If OCR reads:

```text
1,800.00
```

as:

```text
1,600.00
```

balance reconciliation may catch the error.

---

# 37. Security and privacy model

Bank statements are sensitive documents.

Current design decisions:

- do not commit statements to GitHub;
- process uploads in application memory;
- do not log statement text intentionally;
- do not send statement content to an LLM API;
- do not require a database;
- hash account identifiers for comparison;
- generated outputs are created for download.

Before wider public use, stronger identity/access management would deserve more attention.

For family use, the current frontend supports an optional `APP_PASSCODE` environment variable. On Replit, this should be stored as a Secret rather than committed to GitHub. The passcode is only a lightweight family-use gate, not enterprise authentication.

For a small family-use MVP, minimizing storage and external services keeps the architecture much simpler.

---

# 38. Suggested reading order

If you want to understand the code without becoming overwhelmed, read in this exact order.

## Step 1

Read:

```text
UNDERSTANDING_THE_PROJECT.md
```

You are here.

## Step 2

Read:

```text
src/consolidated_state/models.py
```

Understand the data structures.

## Step 3

Read:

```text
src/consolidated_state/pdf_inspect.py
src/consolidated_state/layout.py
```

Understand how a PDF becomes structured page information.

## Step 4

Read:

```text
src/consolidated_state/parser.py
```

Understand the strategy registry.

Do **not** immediately dive into every parser detail.

## Step 5

Read:

```text
src/consolidated_state/generic_parsers.py
```

Now the complex code will make more sense.

Focus first on:

```text
LedgerColumnsStrategy
SectionedAmountStrategy
SignedAmountBalanceStrategy
```

## Step 6

Read:

```text
src/consolidated_state/validate.py
src/consolidated_state/readiness.py
```

Understand why a successful parse is not automatically accepted.

## Step 7

Read:

```text
src/consolidated_state/consolidate.py
src/consolidated_state/export_excel.py
src/consolidated_state/export_pdf.py
```

Understand how normalized data becomes the final report.

## Step 8

Read:

```text
src/consolidated_state/pipeline.py
```

This is where all of the modules are assembled into one end-to-end workflow.

## Step 9

Finally read:

```text
app.py
src/consolidated_state/access.py
```

At this point the browser UI and optional family-passcode gate should make sense.

## Step 10

Read:

```text
tests/
```

Tests show concrete examples of what every module is expected to do.

---

# 39. A complete example from beginning to end

Imagine the user uploads:

```text
August.pdf
September.pdf
```

## Stage A — upload

`app.py` gets both PDF byte arrays.

## Stage B — pre-flight

`pdf_inspect.py` checks each file.

Suppose both return:

```text
TEXT_READY
```

Their hashes differ, so they are not exact duplicates.

## Stage C — layout

`layout.py` reads word coordinates.

August might contain:

```text
Date | Details | Debit | Credit | Balance
```

September might contain the same concepts using:

```text
Posting Date | Description | Withdrawals | Deposits | Running Balance
```

Both can still map to the same generic two-sided ledger strategy.

## Stage D — parsing

Each visible row becomes a `Transaction`.

August:

```text
100 transactions
```

September:

```text
87 transactions
```

## Stage E — normalization

Both sets now use identical fields:

```text
date
description
debit
credit
balance
source_file
statement_period
```

## Stage F — validation

The program verifies:

```text
August opening + credits - debits = August closing
September opening + credits - debits = September closing
August closing = September opening
no conflicting currency
same detected account
no unexpected overlap
```

## Stage G — consolidation

The 187 transactions are combined and sorted chronologically.

## Stage H — summaries

The program calculates:

```text
August deposits
August withdrawals
September deposits
September withdrawals
overall deposits
overall withdrawals
net change
```

## Stage I — final gate

If everything passes:

```text
safe_to_export = True
```

## Stage J — outputs

The user receives:

```text
consolidated_bank_statement_report.xlsx
consolidated_bank_statement_report.pdf
```

That is the complete product.

---

# 40. What is finished now?

The current foundation includes:

- polished Streamlit web application;
- optional family passcode using the `APP_PASSCODE` environment secret;
- testable end-to-end processing pipeline;
- PDF upload;
- duplicate-file hashing;
- invalid/encrypted PDF checks;
- embedded-text detection;
- coordinate-aware layout extraction;
- metadata extraction;
- generic layout strategy system;
- multiple ledger/layout families;
- international date safety;
- Decimal financial arithmetic;
- transaction normalization;
- duplicate/overlap checks;
- statement reconciliation;
- cross-statement validation;
- Excel report;
- PDF report;
- automated pytest suite;
- GitHub Actions;
- Replit runtime configuration.

---

# 41. What is not finished yet?

Important remaining work includes:

## More real-world format testing

Every new representative statement helps reveal structural cases we have not seen.

## OCR

Image-only/scanned statements currently stop safely.

## Frontend polish

The application works, but the interface can be made simpler and more visually clear for a non-technical user.

## Deployment verification

Before handing the link to your dad:

- all tests must be green;
- real examples must pass;
- the Replit published URL must be tested;
- privacy behavior should be reviewed.

## Authentication

For a private family tool, we should consider whether the published URL needs a simple access-control layer.

That decision depends on how Replit publication is configured and how sensitive the intended use is.

---

# 42. What should you understand for a project explanation?

If someone asks you:

> What did you build?

A good answer is:

> We built a bank-agnostic financial document-processing web application. A user uploads multiple bank-statement PDFs. The system uses PDF geometry to detect common transaction-table layouts, normalizes transactions into a common schema, validates the extraction using balance reconciliation and cross-statement checks, then produces consolidated Excel and PDF reports. It is deterministic rather than LLM-based because exact financial amounts must not be hallucinated.

If someone asks:

> Why is it bank-agnostic?

Answer:

> Parsers are selected by document structure—such as debit/credit ledger columns or separated deposit/withdrawal sections—not by bank name.

If someone asks:

> Why no AI model?

Answer:

> The core task is exact structured extraction and arithmetic. Deterministic parsing plus reconciliation is safer and cheaper. An LLM could later help with optional categorization, but not with source-of-truth financial values.

If someone asks:

> What makes it trustworthy?

Answer:

> The system fails closed. A document that cannot be interpreted or reconciled blocks export instead of silently producing an incomplete report.

---

# 43. The core philosophy

The most important design rule in this entire project is:

```text
Correct and incomplete
is better than
complete-looking and wrong.
```

That rule explains why we:

- reject unsupported layouts;
- reject ambiguous dates;
- reject unprovable debit/credit direction;
- use Decimal;
- reconcile balances;
- track statement periods;
- detect duplicate files;
- keep validation separate from parsing;
- block partial exports.

That is the foundation of the application.

---

# 44. One-sentence mental model

If you remember only one sentence, remember this:

> **ConsolidatedState converts different visual bank-statement layouts into one common transaction schema, proves the extracted numbers are internally consistent, and only then creates one consolidated report.**
