# CODE EXECUTION MAP — Complete Self-Contained Walkthrough

This is the third learning document for ConsolidatedState.

Use this file when the main problem is:

> "I understand individual explanations, but I lose track because one file calls a function in another file, which creates an object from another class, which returns somewhere else."

This guide solves that by following the real execution path in one direction.

**You do not need to open the Python files while reading this guide.** The important code blocks from each file are included directly below, followed by detailed explanations of what they receive, what they do, why they exist, what they return, and what runs next.

Some purely visual CSS, repetitive formatting code, and test-fixture boilerplate are intentionally omitted because they are not necessary to understand how the application works. The important execution and financial-processing code is included here.

Read this document from top to bottom. The file names are chapter labels, not instructions to leave this document.

---

# How to use this document

Treat this Markdown file as the codebase walkthrough itself.

When a block calls a function from another file, I will:

~~~text
1. show the caller code;
2. explain the arguments;
3. show the important called code here in this document;
4. explain its return value;
5. continue the caller afterward.
~~~

You therefore do not need to keep switching tabs between Python files.

A good question to keep asking is:

~~~text
"What object do we have right now,
and what function receives it next?"
~~~

The most important data-shape transitions are:

~~~text
UploadedFile
    ↓
(filename, PDF bytes)
    ↓
PdfInspection + plain text
    ↓
DocumentLayout
    ↓
ParseResult
    ↓
list[Transaction]
    ↓
pandas DataFrame
    ↓
validation tables
    ↓
Excel/PDF bytes
    ↓
ConsolidationResult
    ↓
browser
~~~

---

# Master code-flow skeleton before the detailed walkthrough

This is not a different implementation. It is a compressed view of the real current code so you can see the whole call chain before studying each block.

~~~python
# app.py

uploaded_files = st.file_uploader(
    "Upload bank statement PDFs",
    type=["pdf"],
    accept_multiple_files=True,
)

if st.button("Process statements"):
    inputs = [
        (uploaded.name, uploaded.getvalue())
        for uploaded in uploaded_files
    ]

    st.session_state["consolidation_result"] = (
        process_statements(inputs)
    )
~~~

That calls the backend workflow:

~~~python
# pipeline.py

def process_statements(files):
    for source_file, pdf_bytes in files:

        inspection, text = inspect_and_extract_pdf(
            pdf_bytes,
            source_file,
        )

        if inspection.status != "TEXT_READY":
            continue

        parsed = parse_statement(
            text,
            source_file,
            pdf_bytes=pdf_bytes,
        )

        all_transactions.extend(
            parsed.transactions
        )

        statement_summaries.append(
            parsed.statement
        )

    transaction_frame = transactions_to_frame(
        all_transactions
    )

    validation_rows.append(
        validate_transaction_rows(
            transaction_frame
        )
    )

    validation_rows.extend(
        validate_statement_set(
            statement_summaries
        )
    )

    for statement in statement_summaries:
        validation_rows.append(
            reconcile_statement(
                statement,
                transaction_frame,
            )
        )

    safe, reasons = export_is_safe(
        validation_frame,
        uploaded_file_count=len(files),
        parsed_file_count=len(parsed_files),
    )

    if safe:
        excel_report = build_excel_report(...)
        pdf_report = build_pdf_report(...)

    return ConsolidationResult(...)
~~~

The PDF intake called above is:

~~~python
# pdf_inspect.py

with fitz.open(
    stream=pdf_bytes,
    filetype="pdf"
) as document:

    text = "\n".join(
        page.get_text("text")
        for page in document
    )
~~~

The parser then creates geometry from the same PDF bytes:

~~~python
# parser.py

layout = extract_document_layout(
    pdf_bytes
)

for parser in PARSERS:
    if not parser.matches(layout):
        continue

    return _enrich_result(
        parser.parse(
            layout,
            source_file
        ),
        layout,
    )
~~~

Geometry extraction is:

~~~python
# layout.py

page.get_text("words")
    ↓
_group_words_into_rows(...)
    ↓
PageLayout
    ↓
DocumentLayout
~~~

The generic strategy eventually creates:

~~~python
Transaction(
    transaction_date,
    description,
    debit=debit,
    credit=credit,
    balance=balance,
    source_file=source_file,
)
~~~

Everything after that works on normalized Transaction objects rather than raw PDF geometry.

Now the detailed walkthrough begins.


# 1. The complete file order

This document walks through the files in this order:

~~~text
0. .replit
1. .streamlit/config.toml
2. src/consolidated_state/models.py
3. app.py
4. src/consolidated_state/access.py
5. src/consolidated_state/pipeline.py
6. src/consolidated_state/pdf_inspect.py
7. src/consolidated_state/layout.py
8. src/consolidated_state/parser.py
9. src/consolidated_state/metadata.py
10. src/consolidated_state/generic_parsers.py
11. src/consolidated_state/consolidate.py
12. src/consolidated_state/validate.py
13. src/consolidated_state/readiness.py
14. src/consolidated_state/report_data.py
15. src/consolidated_state/export_excel.py
16. src/consolidated_state/export_pdf.py
17. back to app.py
18. tests/
~~~

This is not alphabetical order.

It is the order that best matches how the running program works.

---

# 2. The master execution map

Here is the entire program as one path:

~~~text
Replit starts process
    ↓
.replit
    ↓
streamlit run app.py
    ↓
app.py renders page
    ↓
user uploads PDFs
    ↓
uploaded.getvalue()
    ↓
(filename, pdf_bytes)
    ↓
process_statements(...)
    ↓
pipeline.py

FOR EACH PDF:
    ↓
inspect_and_extract_pdf(...)
    ↓
pdf_inspect.py
    ↓
PdfInspection + flat text
    ↓
back to pipeline.py
    ↓
parse_statement(...)
    ↓
parser.py
    ↓
extract_document_layout(...)
    ↓
layout.py
    ↓
DocumentLayout
    ↓
back to parser.py
    ↓
try strategy.matches(...)
    ↓
generic_parsers.py
    ↓
strategy.parse(...)
    ↓
Transaction objects + StatementSummary
    ↓
back to parser.py
    ↓
extract_statement_metadata(...)
    ↓
metadata.py
    ↓
enriched ParseResult
    ↓
back to pipeline.py

AFTER ALL PDFS:
    ↓
transactions_to_frame(...)
    ↓
consolidate.py
    ↓
validate_transaction_rows(...)
    ↓
validate_statement_set(...)
    ↓
reconcile_statement(...)
    ↓
validate.py
    ↓
monthly_summary(...)
    ↓
consolidate.py
    ↓
export_is_safe(...)
    ↓
readiness.py

IF SAFE:
    ↓
build_excel_report(...)
    ↓
export_excel.py

    AND

    build_pdf_report(...)
    ↓
export_pdf.py

    ↓
ConsolidationResult
    ↓
back to app.py
    ↓
render_result(...)
    ↓
browser tables + download buttons
~~~

Keep this map in mind while reading the sections below. All necessary code excerpts are in this document.

---

# 3. Rule for reading code that calls another file

Whenever you see a call such as:

~~~python
inspection, text = inspect_and_extract_pdf(pdf_bytes, source_file)
~~~

do not mentally jump everywhere at once.

Use this sequence:

~~~text
1. Pause caller.
2. Ask: what arguments are being sent?
3. Open the called function.
4. Understand only that function.
5. Ask: what does it return?
6. Return mentally to the caller.
7. Continue on the next line.
~~~

This is exactly how we will read the project below.

---

# 4. File 0 — .replit

This file answers:

> "How does the application even start?"

Important block:

~~~text
[[workflows.workflow.tasks]]
task = "shell.exec"
args = "streamlit run app.py --server.address 0.0.0.0 --server.port 5000 --server.headless true --browser.gatherUsageStats false"
waitForPort = 5000
~~~

Meaning:

~~~text
Replit presses Run
    ↓
shell command executes
    ↓
streamlit run app.py
    ↓
Python executes app.py
~~~

This file does not parse PDFs.

It only tells Replit how to launch the app.

Also:

~~~text
[[ports]]
localPort = 5000
externalPort = 80
~~~

means Streamlit listens internally on port 5000, and Replit exposes the web app externally.

## What we have after this file

A running Python/Streamlit process executing app.py.

## The next section below covers

~~~text
.streamlit/config.toml
~~~

---

# 5. File 1 — .streamlit/config.toml

Important block:

~~~toml
[server]
headless = true
address = "0.0.0.0"
port = 5000
maxUploadSize = 20

[browser]
gatherUsageStats = false
~~~

Meaning:

~~~text
headless = true
    run as server, not desktop GUI

address = 0.0.0.0
    listen on network interfaces

port = 5000
    Streamlit server port

maxUploadSize = 20
    Streamlit upload limit in MB
~~~

This still does not parse anything.

It is runtime configuration.

## What we have after this file

A Streamlit server ready to execute app.py.

## The next section below covers

~~~text
src/consolidated_state/models.py
~~~

---

# 6. File 2 — models.py

Read this BEFORE the pipeline.

Why?

Because almost every other file creates or returns one of these objects.

Current important code:

~~~python
@dataclass(frozen=True)
class Transaction:
    date: date
    description: str
    debit: Decimal | None = None
    credit: Decimal | None = None
    balance: Decimal | None = None
    source_file: str = ""
    statement_period: str = ""
~~~

This is the shape of ONE normalized transaction.

Example:

~~~python
Transaction(
    date=date(2026, 1, 14),
    description="Coffee Shop",
    debit=Decimal("5.00"),
    credit=None,
    balance=Decimal("1095.00"),
    source_file="January.pdf",
    statement_period="2026-01-01 to 2026-01-31",
)
~~~

Important idea:

Different banks may use different words:

~~~text
Debit
Withdrawal
Money Out
~~~

but our normalized object always uses:

~~~text
debit
~~~

That is how consolidation becomes possible.

---

# 7. StatementSummary

Current code:

~~~python
@dataclass(frozen=True)
class StatementSummary:
    source_file: str
    statement_period: str = ""
    opening_balance: Decimal | None = None
    closing_balance: Decimal | None = None
    statement_start: date | None = None
    statement_end: date | None = None
    account_fingerprint: str | None = None
    currency: str | None = None
    layout_strategy: str = ""
~~~

This is information about the WHOLE statement.

Do not confuse:

~~~text
Transaction
    one row

StatementSummary
    one PDF statement
~~~

Example:

~~~text
source_file
    January.pdf

statement_period
    2026-01-01 to 2026-01-31

opening_balance
    1000.00

closing_balance
    1095.00

currency
    USD

layout_strategy
    ledger-two-sided-columns-v2
~~~

---

# 8. ParseResult

Code:

~~~python
@dataclass(frozen=True)
class ParseResult:
    transactions: list[Transaction]
    statement: StatementSummary
    parser_name: str
~~~

This bundles together the result of parsing ONE PDF.

Conceptually:

~~~text
ParseResult
    │
    ├── transactions
    │     ├── Transaction 1
    │     ├── Transaction 2
    │     └── Transaction 3
    │
    ├── statement
    │     └── StatementSummary
    │
    └── parser_name
          "ledger-two-sided-columns-v2"
~~~

This object travels from generic_parsers.py back to parser.py and then back to pipeline.py.

---

# 9. PdfInspection

Code:

~~~python
@dataclass(frozen=True)
class PdfInspection:
    source_file: str
    sha256: str
    size_bytes: int
    page_count: int
    encrypted: bool
    has_text: bool
    status: str
    detail: str
~~~

This is NOT transaction data.

It describes whether the uploaded file is readable.

Example:

~~~text
source_file = January.pdf
page_count = 4
encrypted = False
has_text = True
status = TEXT_READY
~~~

## What we have after models.py

You now know the main object types the rest of the program passes around.

## The next section below covers

~~~text
app.py
~~~

---

# 10. File 3 — app.py imports

At the top:

~~~python
from consolidated_state.access import passcode_matches
from consolidated_state.pipeline import ConsolidationResult, process_statements
~~~

This tells you app.py does not perform financial parsing itself.

It relies on:

~~~text
access.py
    passcode logic

pipeline.py
    complete document-processing workflow
~~~

Do not mentally jump into pipeline.py yet; this document will reach it in order.

First understand what app.py sends into it; the pipeline code is included later in this document.

---

# 11. app.py optional access gate

app.py eventually calls:

~~~python
require_optional_passcode()
~~~

Inside:

~~~python
configured = os.getenv("APP_PASSCODE", "").strip()
~~~

This checks an environment variable.

If no passcode exists:

~~~python
if not configured:
    ...
    return
~~~

If one exists, app.py eventually calls:

~~~python
if passcode_matches(supplied, configured):
~~~

Pause the current call here.

The next section below contains the important code from:

~~~text
src/consolidated_state/access.py
~~~

---

# 12. File 4 — access.py

Entire important function:

~~~python
def passcode_matches(
    supplied: str,
    configured: str,
) -> bool:
    if not configured:
        return True

    return hmac.compare_digest(
        supplied.encode("utf-8"),
        configured.encode("utf-8"),
    )
~~~

Inputs:

~~~text
supplied
    what user typed

configured
    APP_PASSCODE from environment
~~~

Output:

~~~text
True
or
False
~~~

After this function returns, execution resumes in the app.py section immediately below.

---

# 13. Back to app.py — upload widget

Important block:

~~~python
uploaded_files = st.file_uploader(
    "Upload bank statement PDFs",
    type=["pdf"],
    accept_multiple_files=True,
    help="Select up to 12 PDF statements. Each file can be up to 20 MB.",
    key="statement_uploads",
    on_change=clear_previous_result,
)
~~~

This is where the browser lets the user select PDF files.

Suppose the user selects:

~~~text
August.pdf
September.pdf
~~~

uploaded_files contains two Streamlit UploadedFile objects.

Still no parsing has happened.

---

# 14. app.py — Process statements button

Important block:

~~~python
if st.button(
    "Process statements",
    type="primary",
    use_container_width=True,
):
~~~

Nothing is processed until this button becomes True during a Streamlit run.

Inside:

~~~python
inputs = [
    (uploaded.name, uploaded.getvalue())
    for uploaded in uploaded_files
]
~~~

This is the first major transformation.

For each UploadedFile:

~~~text
uploaded.name
    filename string

uploaded.getvalue()
    raw PDF bytes
~~~

So inputs becomes conceptually:

~~~python
[
    ("August.pdf", AUGUST_PDF_BYTES),
    ("September.pdf", SEPTEMBER_PDF_BYTES),
]
~~~

Long version of the comprehension:

~~~python
inputs = []

for uploaded in uploaded_files:
    pair = (
        uploaded.name,
        uploaded.getvalue(),
    )
    inputs.append(pair)
~~~

Same result.

---

# 15. app.py — the handoff to the backend workflow

Critical line:

~~~python
st.session_state["consolidation_result"] = (
    process_statements(inputs)
)
~~~

Pause app.py here.

This is the major jump.

We send:

~~~text
inputs
    list of:
        (filename, PDF bytes)
~~~

into:

~~~text
process_statements()
~~~

The next section below contains the important code from:

~~~text
src/consolidated_state/pipeline.py
~~~

---

# 16. File 5 — pipeline.py imports

At the top, pipeline.py imports almost every backend component.

Conceptually:

~~~text
pipeline.py
    │
    ├── consolidate.py
    ├── export_excel.py
    ├── export_pdf.py
    ├── models.py
    ├── parser.py
    ├── pdf_inspect.py
    ├── readiness.py
    ├── report_data.py
    └── validate.py
~~~

This file is the conductor.

The other modules are specialists.

Pipeline says:

~~~text
"Inspect this."
"Parse this."
"Validate this."
"Summarize this."
"Export this."
~~~

---

# 17. ConsolidationResult

Before process_statements(), pipeline.py defines:

~~~python
@dataclass
class ConsolidationResult:
    inspections: pd.DataFrame
    statements: pd.DataFrame
    transactions: pd.DataFrame
    monthly_summary: pd.DataFrame
    validation: pd.DataFrame
    safe_to_export: bool
    blocking_reasons: list[str]
    excel_report: bytes | None
    pdf_report: bytes | None
    total_credits: Decimal
    total_debits: Decimal
~~~

This is the final object pipeline.py gives back to app.py.

Think:

~~~text
process_statements(...)
    ↓
ConsolidationResult
    ├── everything needed for browser tables
    ├── validation result
    ├── Excel bytes
    └── PDF bytes
~~~

---

# 18. process_statements() input

Signature:

~~~python
def process_statements(
    files: list[tuple[str, bytes]],
) -> ConsolidationResult:
~~~

Read inside-out:

~~~text
tuple[str, bytes]
    =
(filename, pdf bytes)

list[tuple[str, bytes]]
    =
many uploaded PDFs
~~~

That is exactly what app.py created.

---

# 19. Pipeline safety checks

First:

~~~python
if not files:
    raise ValueError("At least one PDF statement is required.")

if len(files) > 12:
    raise ValueError("No more than 12 statements can be processed at once.")
~~~

These are whole-request checks.

If invalid, the function stops immediately.

---

# 20. Pipeline's temporary containers

Important initialization:

~~~python
inspections: list[dict[str, object]] = []
all_transactions = []
statement_summaries: list[StatementSummary] = []
validation_rows: list[dict[str, object]] = []
seen_hashes: dict[str, str] = {}
parsed_files: set[str] = set()
~~~

Keep this table in mind:

| Variable | What it collects |
|---|---|
| inspections | file-level intake information |
| all_transactions | every Transaction from every parsed PDF |
| statement_summaries | one StatementSummary per parsed PDF |
| validation_rows | validation messages |
| seen_hashes | SHA-256 hash → first filename |
| parsed_files | names of PDFs that successfully parsed |

This is where much of the data accumulates.

---

# 21. Pipeline's most important loop

Code:

~~~python
for source_file, pdf_bytes in files:
~~~

If files is:

~~~python
[
    ("August.pdf", AUGUST_BYTES),
    ("September.pdf", SEPTEMBER_BYTES),
]
~~~

iteration 1:

~~~text
source_file = "August.pdf"
pdf_bytes = AUGUST_BYTES
~~~

iteration 2:

~~~text
source_file = "September.pdf"
pdf_bytes = SEPTEMBER_BYTES
~~~

Everything immediately below happens once per uploaded PDF.

---

# 22. Pipeline calls PDF inspection

Critical line:

~~~python
inspection, text = inspect_and_extract_pdf(
    pdf_bytes,
    source_file,
)
~~~

Pause pipeline.py here.

Inputs being sent:

~~~text
pdf_bytes
    full PDF binary contents

source_file
    filename
~~~

Expected return:

~~~text
(
    PdfInspection,
    plain text string
)
~~~

The next section below contains the important code from:

~~~text
src/consolidated_state/pdf_inspect.py
~~~

---

# 23. File 6 — pdf_inspect.py imports

Important:

~~~python
import hashlib
import fitz

from .models import PdfInspection
~~~

hashlib:
    SHA-256 hashing.

fitz:
    PyMuPDF.

PdfInspection:
    the dataclass you already read.

---

# 24. sha256_bytes()

Code:

~~~python
def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
~~~

Input:

~~~text
raw PDF bytes
~~~

Output:

~~~text
hexadecimal SHA-256 string
~~~

Purpose:

Detect exact duplicate files.

This hash is based on bytes, not filename.

---

# 25. inspect_and_extract_pdf() first lines

Code:

~~~python
digest = sha256_bytes(pdf_bytes)
size_bytes = len(pdf_bytes)
~~~

Now we know:

~~~text
digest
    exact-file fingerprint

size_bytes
    PDF byte length
~~~

Then checks:

~~~python
if size_bytes == 0:
    ...
~~~

and:

~~~python
if size_bytes > MAX_PDF_BYTES:
    ...
~~~

If either condition returns, nothing below executes for that PDF.

---

# 26. Opening the PDF using PyMuPDF

Critical block:

~~~python
with fitz.open(
    stream=pdf_bytes,
    filetype="pdf"
) as document:
~~~

This converts the raw bytes into a PyMuPDF Document object.

Very important:

We are not opening a saved path.

We are opening the in-memory bytes.

The with statement ensures the PyMuPDF document object is closed after the block.

---

# 27. Password check

Code:

~~~python
page_count = document.page_count

if document.needs_pass:
    return (
        PdfInspection(...),
        "",
    )
~~~

If encrypted, return immediately.

No parser runs.

---

# 28. Plain-text extraction

This is the exact line:

~~~python
text = "\n".join(
    page.get_text("text")
    for page in document
)
~~~

Break it down.

Part A:

~~~python
for page in document
~~~

visits every page.

Part B:

~~~python
page.get_text("text")
~~~

is a PyMuPDF Page method.

It asks PyMuPDF to extract the page's embedded text as ordinary text.

Part C:

~~~python
"\n".join(...)
~~~

combines all page strings into one large string.

Example:

~~~text
page 1 text
\n
page 2 text
\n
page 3 text
~~~

Important:

This plain text is NOT currently the primary transaction-table parser input.

It is mainly used to determine whether embedded text exists.

---

# 29. Detecting scanned/image-only PDFs

Code:

~~~python
has_text = bool(text.strip())
~~~

If text only contains whitespace:

~~~text
has_text = False
~~~

Then:

~~~text
status = OCR_REQUIRED
~~~

If embedded text exists:

~~~text
status = TEXT_READY
~~~

The current human-readable detail string still says "bank-specific parser"; that is leftover wording. The actual parser architecture is generic by layout.

---

# 30. pdf_inspect.py return

Successful result:

~~~python
return (
    PdfInspection(
        ...
    ),
    text,
)
~~~

Two values.

Execution now returns to:

~~~text
pipeline.py
~~~

where we had:

~~~python
inspection, text = inspect_and_extract_pdf(...)
~~~

So now:

~~~text
inspection
    PdfInspection object

text
    giant plain text string
~~~

---

# 31. Back to pipeline.py — duplicate-file detection

Code:

~~~python
duplicate_of = seen_hashes.get(
    inspection.sha256
)
~~~

seen_hashes is a dictionary:

~~~text
SHA-256 → filename
~~~

If no existing entry:

~~~python
seen_hashes[inspection.sha256] = source_file
~~~

If there is an existing entry:

~~~text
same bytes were uploaded before
~~~

and status becomes:

~~~text
DUPLICATE_FILE
~~~

---

# 32. Pipeline records inspection and validation rows

Pipeline appends dictionaries such as:

~~~python
inspections.append(
    {
        "source_file": inspection.source_file,
        "pages": inspection.page_count,
        "size_mb": ...,
        "embedded_text": inspection.has_text,
        "status": intake_status,
        "detail": intake_detail,
    }
)
~~~

That dictionary later becomes a pandas DataFrame row.

It also appends a validation message.

This is why you see lists of dictionaries in the code.

They are being accumulated so pandas can later create tables.

---

# 33. Skip unusable PDFs

Code:

~~~python
if duplicate_of or inspection.status != "TEXT_READY":
    continue
~~~

Meaning:

If:

~~~text
duplicate
OR
not text-ready
~~~

then stop processing this PDF and go to the next file in the outer loop.

continue does NOT exit process_statements().

It only advances to the next PDF.

---

# 34. Pipeline calls parse_statement()

Critical block:

~~~python
parsed = parse_statement(
    text,
    source_file,
    pdf_bytes=pdf_bytes,
)
~~~

STOP pipeline.py again.

Input:

~~~text
text
    flat text string

source_file
    filename

pdf_bytes
    original PDF bytes
~~~

The next section below contains the important code from:

~~~text
src/consolidated_state/parser.py
~~~

---

# 35. File 7? No — first read layout.py before parser logic

There is an important learning trick.

parser.py immediately calls layout.py.

So before understanding the strategy registry deeply, first understand what a DocumentLayout is.

Open:

~~~text
src/consolidated_state/layout.py
~~~

---

# 36. File 7 — layout.py data model

LayoutWord:

~~~python
@dataclass(frozen=True)
class LayoutWord:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
~~~

Each word now contains:

~~~text
text
AND
position on page
~~~

Example:

~~~text
text = "Coffee"
x0 = 150
y0 = 220
x1 = 185
y1 = 232
~~~

---

# 37. Coordinate system

Think of a PDF page:

~~~text
(0,0) top-left

x increases →
y increases ↓
~~~

Example table:

~~~text
x≈40          x≈150        x≈400     x≈470     x≈540

Date          Description  Debit     Credit    Balance
01/14/26      Coffee       5.00                1095.00
~~~

Geometry lets code infer columns.

---

# 38. LayoutRow

Code:

~~~python
@dataclass(frozen=True)
class LayoutRow:
    y: float
    words: tuple[LayoutWord, ...]

    @property
    def text(self) -> str:
        return " ".join(
            word.text
            for word in self.words
        )
~~~

A row groups words that are visually on approximately the same horizontal line.

Example:

~~~text
LayoutRow
    y = 220
    words =
        01/14/26
        Coffee
        5.00
        1095.00
~~~

row.text becomes:

~~~text
01/14/26 Coffee 5.00 1095.00
~~~

---

# 39. PageLayout and DocumentLayout

PageLayout:

~~~python
@dataclass(frozen=True)
class PageLayout:
    page_number: int
    width: float
    height: float
    rows: tuple[LayoutRow, ...]
~~~

DocumentLayout:

~~~python
@dataclass(frozen=True)
class DocumentLayout:
    pages: tuple[PageLayout, ...]
~~~

Hierarchy:

~~~text
DocumentLayout
    ↓
PageLayout
    ↓
LayoutRow
    ↓
LayoutWord
~~~

This is the central structured representation used by parsers.

---

# 40. Extracting words with coordinates

Critical line inside extract_document_layout():

~~~python
rows=_group_words_into_rows(
    page.get_text("words")
)
~~~

Compare:

~~~text
pdf_inspect.py:
    page.get_text("text")

layout.py:
    page.get_text("words")
~~~

These are two different PyMuPDF extraction modes.

"words" gives word records with coordinates.

Conceptually:

~~~python
(
    x0,
    y0,
    x1,
    y1,
    "Coffee",
    ...
)
~~~

---

# 41. _group_words_into_rows(): sorting

First:

~~~python
ordered = sorted(
    raw_words,
    key=lambda word: (
        word[1],
        word[0]
    )
)
~~~

word[1] = Y.

word[0] = X.

So sort:

~~~text
first top-to-bottom
then left-to-right
~~~

---

# 42. Temporary row structure

Code:

~~~python
working: list[dict[str, object]] = []
~~~

Conceptually:

~~~python
[
    {
        "y": 100.2,
        "words": [
            LayoutWord(...),
            LayoutWord(...),
        ]
    },
    {
        "y": 120.4,
        "words": [
            LayoutWord(...),
        ]
    }
]
~~~

This is only temporary while building rows.

---

# 43. Looping through every raw word

Code:

~~~python
for raw in ordered:
    word = LayoutWord(
        float(raw[0]),
        float(raw[1]),
        float(raw[2]),
        float(raw[3]),
        str(raw[4]),
    )
~~~

Translation:

~~~text
raw[0] → x0
raw[1] → y0
raw[2] → x1
raw[3] → y1
raw[4] → text
~~~

We convert PyMuPDF's tuple into our own clearer object.

---

# 44. Finding which visual row owns the word

Code:

~~~python
matched = None

for row in working[-8:]:
    if abs(float(row["y"]) - word.y0) <= tolerance:
        matched = row
        break
~~~

Meaning:

Look through the most recent rows.

If their Y position is close enough to the word's Y:

~~~text
same visual line
~~~

The default tolerance is:

~~~text
2.2 PDF coordinate units
~~~

---

# 45. New row versus existing row

If no match:

~~~python
working.append(
    {
        "y": word.y0,
        "words": [word]
    }
)
~~~

If match:

~~~python
words = matched["words"]
words.append(word)
~~~

So words are progressively grouped into horizontal rows.

---

# 46. Final row conversion

After grouping:

~~~python
words.sort(
    key=lambda word: word.x0
)
~~~

sort words left-to-right.

Then:

~~~python
rows.append(
    LayoutRow(
        y=float(row["y"]),
        words=tuple(words)
    )
)
~~~

Finally:

~~~python
return DocumentLayout(
    pages=tuple(pages)
)
~~~

## What exists now

A geometric map of the PDF.

Not pixels.

Not OCR.

A structured tree of embedded PDF words and coordinates.

## Now return to

~~~text
parser.py
~~~

---

# 47. File 8 — parser.py entry point

Function:

~~~python
def parse_statement(
    text: str,
    source_file: str,
    pdf_bytes: bytes | None = None,
) -> ParseResult:
~~~

First surprising line:

~~~python
del text
~~~

Meaning:

The current strategies do not use the flat text string for transaction extraction.

They rely on geometric layout.

Then:

~~~python
layout = extract_document_layout(
    pdf_bytes
)
~~~

You already understand what comes back:

~~~text
DocumentLayout
~~~

---

# 48. Parser strategy registry

Critical code:

~~~python
PARSERS: list[ParserStrategy] = [
    LedgerColumnsStrategy(),
    SignedAmountBalanceStrategy(),
    SectionedAmountStrategy(),
]
~~~

This creates three strategy OBJECTS.

It does not parse anything yet.

Think:

~~~text
PARSERS[0]
    knows two-sided ledger format

PARSERS[1]
    knows Amount + Balance format

PARSERS[2]
    knows sectioned deposits/withdrawals format
~~~

---

# 49. ParserStrategy Protocol

Code:

~~~python
class ParserStrategy(Protocol):
    name: str

    def matches(
        self,
        layout: DocumentLayout
    ) -> bool: ...

    def parse(
        self,
        layout: DocumentLayout,
        source_file: str
    ) -> ParseResult: ...
~~~

This says every strategy should provide:

~~~text
name
matches()
parse()
~~~

For runtime understanding, do not overfocus on Protocol.

It is mainly a type/design contract.

---

# 50. Exact strategy-selection loop

Code:

~~~python
for parser in PARSERS:
    if not parser.matches(layout):
        continue

    try:
        return _enrich_result(
            parser.parse(
                layout,
                source_file
            ),
            layout,
        )
~~~

This is the most important control-flow block in parser.py.

Long form:

~~~text
take LedgerColumnsStrategy object
    ↓
call its matches(layout)
    ↓
false?
    try next object

true?
    call that object's parse(layout, source_file)
    ↓
get ParseResult
    ↓
enrich metadata
    ↓
return
~~~

Once return runs, later strategies are not tried.

---

# 51. Before the generic parser strategies, the next section explains metadata.py

parser.py later calls:

~~~python
extract_statement_metadata(layout)
~~~

You should understand that before the large strategy file.

Open:

~~~text
src/consolidated_state/metadata.py
~~~

---

# 52. File 9 — metadata.py purpose

metadata.py extracts statement-level information.

Not individual transaction rows.

It tries to find:

~~~text
statement start
statement end
account fingerprint
currency
~~~

Entry point:

~~~python
def extract_statement_metadata(
    layout: DocumentLayout
) -> StatementMetadata:
    start, end = _find_statement_period(layout)

    return StatementMetadata(
        statement_start=start,
        statement_end=end,
        account_fingerprint=_find_account_fingerprint(layout),
        currency=_find_currency(layout),
    )
~~~

This one function calls three helpers.

Read those helpers one at a time.

---

# 53. _find_statement_period()

Core nested loops:

~~~python
for page in layout.pages:
    for row in page.rows:
~~~

That means:

~~~text
page 1
    row 1
    row 2
    ...

page 2
    row 1
    row 2
~~~

Each row already has:

~~~text
row.text
row.words
~~~

thanks to layout.py.

---

# 54. Token-style dates

Code:

~~~python
token_dates = [
    parsed
    for word in row.words
    if (
        parsed := _parse_token_date(
            word.text
        )
    ) is not None
]
~~~

Long form:

~~~python
token_dates = []

for word in row.words:
    parsed = _parse_token_date(
        word.text
    )

    if parsed is not None:
        token_dates.append(parsed)
~~~

This looks for date-shaped words in the row.

---

# 55. Regex range matching

Example:

~~~python
match = long_date.search(row.text)

if match:
    start = _parse_long_date(
        match.group(1)
    )
    end = _parse_long_date(
        match.group(2)
    )
~~~

If row is:

~~~text
January 1, 2026 to January 31, 2026
~~~

regex capture groups are conceptually:

~~~text
group(0)
    entire matching range

group(1)
    January 1, 2026

group(2)
    January 31, 2026
~~~

That is what group(1) and group(2) mean.

---

# 56. Account fingerprint

Core block:

~~~python
for page in layout.pages[:3]:
    for row in page.rows:
        match = label.search(row.text)

        if not match:
            continue
~~~

layout.pages[:3] means only first three pages.

If regex finds:

~~~text
Account ending in 4321
~~~

then:

~~~python
candidate = ...
~~~

extracts the matched account-like portion.

Then:

~~~python
digest = hashlib.sha256(
    f"account::{candidate.upper()}".encode("utf-8")
).hexdigest()

return digest[:20]
~~~

So actual account text becomes a hash fingerprint.

The report does not need the raw identifier.

---

# 57. Currency extraction

Core idea:

~~~python
for page in layout.pages[:3]:
    for row in page.rows:
        normalized = _normalize(row.text)

        if "currency" not in normalized and "ccy" not in normalized:
            continue
~~~

Only rows that look like currency metadata are considered.

Then words are uppercased and checked against:

~~~text
ISO_CURRENCIES
~~~

Example:

~~~text
Currency: USD
~~~

returns:

~~~text
USD
~~~

## What metadata.py returns

A StatementMetadata object.

Now return mentally to parser.py.

---

# 58. File 10 — generic_parsers.py

This is the hardest file.

Read it in THIS order, not top-to-bottom all at once:

~~~text
A. normalize()
B. parse_date()
C. money_from_words()
D. find_labeled_balance()
E. header alias sets
F. _concept_span()
G. _ledger_header_columns()
H. LedgerColumnsStrategy
I. SignedAmountBalanceStrategy
J. SectionedAmountStrategy
~~~

You can ignore helpers not involved in the current strategy until needed.

---

# 59. normalize()

Code:

~~~python
def normalize(value: str) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        value.lower()
    )
~~~

Examples:

~~~text
"DEBIT"
    → "debit"

"Money Out"
    → "moneyout"

"Running Balance:"
    → "runningbalance"
~~~

Purpose:

Ignore capitalization, spaces, and punctuation for structural matching.

---

# 60. parse_date()

The function first tries explicit formats.

Then numeric regex:

~~~python
NUMERIC_DATE = re.compile(
    r"^(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})$"
)
~~~

For:

~~~text
13/01/2026
~~~

capture groups:

~~~text
group 1 = 13
group 2 = 01
group 3 = 2026
~~~

If first number > 12:

~~~text
must be day
→ DMY
~~~

If second number > 12:

~~~text
must be day
→ MDY
~~~

If ambiguous:

~~~text
use inferred statement order
or return None
~~~

No guessing.

---

# 61. infer_numeric_date_order()

This function loops:

~~~python
for page in layout.pages:
    for row in page.rows:
        for word in row.words:
~~~

This is a three-level nested loop.

It scans every word looking for numeric date evidence.

Example:

~~~text
13/01/26
~~~

proves:

~~~text
DMY
~~~

If no unambiguous date exists, it can use statement-period metadata.

---

# 62. money_from_words()

Core code:

~~~python
raw = "".join(
    word.text
    for word in words
)

cleaned = re.sub(
    r"[^0-9.]",
    "",
    raw.replace(",", "")
)
~~~

Example:

~~~text
"$1,095.00"
    ↓
"1095.00"
~~~

Then verify format:

~~~python
if not re.fullmatch(
    r"\d+\.\d{2}",
    cleaned
):
    return None
~~~

Finally:

~~~python
return Decimal(cleaned)
~~~

So financial text becomes exact Decimal money.

---

# 63. Header concept dictionaries

Examples:

~~~python
DEBIT_HEADERS = {
    "debit",
    "debits",
    "withdrawal",
    "withdrawals",
    "moneyout",
    "outflow",
    "paidout",
}
~~~

and:

~~~python
CREDIT_HEADERS = {
    "credit",
    "credits",
    "deposit",
    "deposits",
    "moneyin",
    "inflow",
    "additions",
}
~~~

This is not bank-name detection.

It is concept detection.

---

# 64. _concept_span()

Purpose:

Find where a header concept appears horizontally.

Suppose row words are:

~~~text
Posting | Date | Description | Money | Out | Money | In | Running | Balance
~~~

The helper tests groups of:

~~~text
3 words
2 words
1 word
~~~

That is this loop:

~~~python
for width in (3, 2, 1):
~~~

Then:

~~~python
group = words[
    index:index + width
]
~~~

Example width 2:

~~~text
"Money Out"
~~~

Normalize:

~~~text
moneyout
~~~

Match against aliases.

If found, return:

~~~text
(
    left X,
    center X
)
~~~

---

# 65. _ledger_header_columns()

Code concept:

~~~python
concepts = {
    "date": ...,
    "debit": ...,
    "credit": ...,
    "balance": ...,
}
~~~

If any required concept is missing:

~~~python
return None
~~~

If all exist:

~~~python
return {
    key: value
    ...
}
~~~

Example result:

~~~python
{
    "date": (40.0, 60.0),
    "debit": (390.0, 410.0),
    "credit": (465.0, 485.0),
    "balance": (535.0, 565.0),
}
~~~

This dictionary maps semantic meaning to geometry.

---

# 66. LedgerColumnsStrategy.matches()

Code:

~~~python
def matches(
    self,
    layout: DocumentLayout
) -> bool:
    return any(
        self.header(row)
        for page in layout.pages
        for row in page.rows
    )
~~~

Long version:

~~~python
for page in layout.pages:
    for row in page.rows:
        if self.header(row):
            return True

return False
~~~

This only answers:

~~~text
"Does this PDF look like my layout family?"
~~~

It does not create transactions yet.

---

# 67. LedgerColumnsStrategy.parse(): locate header

For each page:

~~~python
header_index = None
header = None
columns = None
~~~

Then:

~~~python
for index, row in enumerate(
    page.rows
):
    detected = _ledger_header_columns(row)

    if detected is not None:
        header_index = index
        header = row
        columns = detected
        break
~~~

After this succeeds, we know:

~~~text
which row is the table header
where debit is
where credit is
where balance is
~~~

---

# 68. Ledger column boundaries

Code:

~~~python
debit_center = columns["debit"][1]
credit_center = columns["credit"][1]
balance_center = columns["balance"][1]
~~~

[1] means second tuple item.

If:

~~~python
columns["debit"] == (390.0, 410.0)
~~~

then:

~~~text
[0] = 390.0 left
[1] = 410.0 center
~~~

Then boundaries:

~~~python
debit_credit_boundary = (
    debit_center + credit_center
) / 2

credit_balance_boundary = (
    credit_center + balance_center
) / 2
~~~

This creates geometric zones.

---

# 69. Ledger transaction-row loop

Important:

~~~python
for row in page.rows[
    header_index + 1:
]:
~~~

Meaning:

Only inspect rows AFTER the table header.

For each row, look for date words:

~~~python
date_words = [
    word
    for word in row.words
    if parse_date(
        word.text,
        date_order
    ) is not None
    and word.x0 < detail_x
]
~~~

A date-looking word on the left suggests:

~~~text
new transaction row
~~~

---

# 70. Selecting debit words by X coordinate

Code:

~~~python
debit = money_from_words(
    [
        word
        for word in row.words
        if debit_left
        <= word.center_x
        < debit_credit_boundary
    ]
)
~~~

Translate:

~~~text
for every word in this row:
    calculate center_x

if center_x lies inside debit region:
    keep it

send retained word(s) to money_from_words()
~~~

Same idea for credit and balance.

This is the heart of geometry parsing.

---

# 71. Selecting description words

Code:

~~~python
description = " ".join(
    word.text
    for word in row.words
    if detail_x - 2
    <= word.x0
    < debit_left
).strip()
~~~

Meaning:

Take text words between:

~~~text
description start
and
debit-column start
~~~

Join them into one string.

---

# 72. Creating Transaction object

Code:

~~~python
current = Transaction(
    transaction_date,
    description,
    debit=debit,
    credit=credit,
    balance=balance,
    source_file=source_file,
)
~~~

At this moment, visual PDF content becomes our normalized business object.

This is one of the most important transitions in the entire application.

~~~text
PDF words + coordinates
        ↓
Transaction
~~~

---

# 73. Multi-line transaction descriptions

If next row has no date:

~~~python
if current is not None:
~~~

the parser may treat it as continuation text.

It extracts description-region words and rebuilds current:

~~~python
current = Transaction(
    current.date,
    f"{current.description} {continuation}".strip(),
    ...
)
~~~

Because Transaction is frozen, we create a new one rather than mutating fields.

---

# 74. Opening and closing balance

After transactions:

~~~python
opening = find_labeled_balance(
    layout,
    (
        "beginningbalance",
        "openingbalance"
    ),
)
~~~

If no labeled opening balance but first running balance exists:

~~~python
opening = (
    first.balance
    + (first.debit or Decimal("0"))
    - (first.credit or Decimal("0"))
)
~~~

This mathematically reconstructs balance before first transaction.

Closing:

~~~python
closing = find_labeled_balance(...)

if closing is None:
    closing = last.balance
~~~

Then strategy returns ParseResult.

---

# 75. SignedAmountBalanceStrategy

Use this layout when PDF has:

~~~text
Date | Description | Amount | Balance
~~~

not separate debit and credit columns.

First, matches() requires:

~~~text
date
amount
balance
~~~

and rejects header if explicit debit/credit columns exist.

---

# 76. Signed strategy direction logic

For each transaction:

~~~python
amount, explicit_direction = (
    _signed_money_from_words(
        amount_words
    )
)
~~~

Possible explicit signals:

~~~text
-100.00
    debit

+100.00
    credit

100.00 DR
    debit

100.00 CR
    credit
~~~

If absent, running balance proves direction.

Example:

~~~text
previous_balance = 1000
amount = 100
balance = 1100

delta = 100

therefore credit
~~~

If direction cannot be proven:

~~~python
raise GenericParseError(...)
~~~

Again: fail closed.

---

# 77. SectionedAmountStrategy

Use for layout:

~~~text
Deposits and other additions

Date | Description | Amount

Withdrawals and other subtractions

Date | Description | Amount
~~~

The key state variable:

~~~python
direction: str | None = None
~~~

When parser sees a section heading:

~~~text
deposits/additions
    direction = credit

withdrawals/subtractions
    direction = debit
~~~

Then each later amount is assigned to that side until section changes.

---

# 78. Sectioned strategy header detection

matches() wants BOTH:

~~~text
Date + Amount header
AND
recognizable money-in/out section
~~~

If both exist:

~~~text
layout family recognized
~~~

Then parse() loops through rows, tracks current section, finds dates, descriptions, and amount position.

---

# 79. Strategy returns ParseResult

All three strategy classes ultimately return the same shape:

~~~python
ParseResult(
    transactions,
    StatementSummary(
        ...
    ),
    self.name,
)
~~~

This is why later pipeline code does not care which layout strategy was used.

Different layout in.

Same normalized object shape out.

---

# 80. Back to parser.py — _enrich_result()

Once strategy.parse() returns:

~~~python
return _enrich_result(
    parser.parse(...),
    layout,
)
~~~

_enrich_result() calls:

~~~python
metadata = extract_statement_metadata(
    layout
)
~~~

You already studied metadata.py.

Then it combines:

~~~text
strategy-derived data
+
statement-level metadata
~~~

using dataclasses.replace().

---

# 81. Updating transaction statement period

Code:

~~~python
transactions = [
    replace(
        transaction,
        statement_period=period
    )
    for transaction in result.transactions
]
~~~

Long form:

~~~python
transactions = []

for transaction in result.transactions:
    updated = replace(
        transaction,
        statement_period=period
    )
    transactions.append(updated)
~~~

Then final ParseResult goes back to pipeline.py.

---

# 82. Back to pipeline.py — successful parse

Now:

~~~python
parsed = parse_statement(...)
~~~

contains:

~~~text
parsed.transactions
parsed.statement
parsed.parser_name
~~~

Pipeline accumulates them:

~~~python
all_transactions.extend(
    parsed.transactions
)

statement_summaries.append(
    parsed.statement
)

parsed_files.add(
    source_file
)
~~~

Important difference:

~~~text
append(x)
    add one item

extend(list)
    add every item from the list
~~~

---

# 83. After the PDF loop finishes

Now all uploaded PDFs have either:

~~~text
failed safely
or
produced normalized transactions
~~~

Pipeline converts collections into tables:

~~~python
inspection_frame = pd.DataFrame(
    inspections
)

transaction_frame = (
    transactions_to_frame(
        all_transactions
    )
)

statement_frame = (
    build_statement_frame(
        statement_summaries
    )
)
~~~

Now we follow these calls.

---

# 84. File 11 — consolidate.py

First important function:

~~~python
def transactions_to_frame(
    transactions: Iterable[Transaction]
) -> pd.DataFrame:
~~~

It turns Transaction objects into row dictionaries.

Core:

~~~python
rows = [
    {
        "date": tx.date,
        "description": tx.description,
        "debit": tx.debit,
        "credit": tx.credit,
        "balance": tx.balance,
        "source_file": tx.source_file,
        "statement_period": tx.statement_period,
    }
    for tx in transactions
]
~~~

Then:

~~~python
frame = pd.DataFrame(
    rows,
    columns=TRANSACTION_COLUMNS
)
~~~

Now we have a pandas table.

---

# 85. Sorting transactions

Code:

~~~python
frame = frame.sort_values(
    ["date", "source_file"],
    kind="stable"
).reset_index(
    drop=True
)
~~~

Purpose:

Put consolidated transactions in chronological order.

---

# 86. Duplicate transaction candidates

find_duplicate_transactions() uses key:

~~~python
key = [
    "date",
    "description",
    "debit",
    "credit",
    "balance",
]
~~~

It finds rows with identical values.

Then it only keeps groups appearing in more than one:

~~~text
source_file
~~~

This avoids automatically calling two legitimate identical purchases within the same statement duplicates.

---

# 87. monthly_summary()

Creates month:

~~~python
work["month"] = (
    work["date"]
    .dt.to_period("M")
    .astype(str)
)
~~~

Then groups:

~~~python
work.groupby(
    "month",
    as_index=False
).agg(
    total_debits=("debit", "sum"),
    total_credits=("credit", "sum")
)
~~~

Then:

~~~python
summary["net"] = (
    summary["total_credits"]
    - summary["total_debits"]
)
~~~

Now return mentally to pipeline.py.

---

# 88. Pipeline begins validation

First:

~~~python
validation_rows.append(
    validate_transaction_rows(
        transaction_frame
    )
)
~~~

Then:

~~~python
validation_rows.extend(
    validate_statement_set(
        statement_summaries
    )
)
~~~

Open:

~~~text
src/consolidated_state/validate.py
~~~

---

# 89. File 12 — validate_transaction_rows()

First guard:

~~~python
if frame.empty:
    return {
        ...
        "status": "FAIL",
        ...
    }
~~~

Then issue counters:

~~~python
issue_counts = {
    "missing_description": 0,
    "missing_source_file": 0,
    "invalid_amount_sides": 0,
    "negative_amount": 0,
}
~~~

Then:

~~~python
for _, row in frame.iterrows():
~~~

loops over every transaction table row.

---

# 90. Exactly one debit/credit side

Core:

~~~python
debit = row.get("debit")
credit = row.get("credit")

has_debit = _is_present(debit)
has_credit = _is_present(credit)

if has_debit == has_credit:
    issue_counts[
        "invalid_amount_sides"
    ] += 1
~~~

Truth table:

~~~text
has_debit  has_credit  equality  meaning
True       False       False     valid
False      True        False     valid
True       True        True      invalid
False      False       True      invalid
~~~

Very compact Python for:

~~~text
exactly one side must exist
~~~

---

# 91. validate_statement_set()

Input:

~~~text
list of StatementSummary
~~~

It checks all statements together.

First account fingerprints:

~~~python
known_accounts = {
    statement.account_fingerprint
    for statement in statements
    if statement.account_fingerprint
}
~~~

If set contains more than one unique value:

~~~text
multiple detected accounts
→ FAIL
~~~

---

# 92. Currency consistency

Same pattern:

~~~python
known_currencies = {
    statement.currency
    for statement in statements
    if statement.currency
}
~~~

If:

~~~text
{"USD", "PKR"}
~~~

then:

~~~text
FAIL
~~~

No currency conversion occurs.

---

# 93. Adjacent statement comparison

Code:

~~~python
ordered = sorted(
    dated,
    key=lambda statement:
        statement.statement_start
)
~~~

Then:

~~~python
for previous, current in zip(
    ordered,
    ordered[1:]
):
~~~

If ordered is:

~~~text
January
February
March
~~~

zip creates:

~~~text
January ↔ February
February ↔ March
~~~

This is how consecutive periods are compared.

---

# 94. Overlap, gaps, continuity

Overlap:

~~~python
if current.statement_start <= previous.statement_end:
~~~

Gap:

~~~python
gap_days = (
    current.statement_start
    - previous.statement_end
).days - 1
~~~

Balance continuity:

~~~python
abs(
    previous.closing_balance
    - current.opening_balance
) > CENT
~~~

These are cross-statement checks.

---

# 95. reconcile_statement()

Core equation:

~~~python
expected_close = (
    statement.opening_balance
    + credits
    - debits
)
~~~

Then:

~~~python
difference = (
    statement.closing_balance
    - expected_close
)
~~~

Then:

~~~python
passed = abs(difference) <= CENT
~~~

This checks whether parsed transaction totals agree with the statement's opening/closing balance.

Now return to pipeline.py.

---

# 96. Pipeline creates validation DataFrame

Code:

~~~python
validation_frame = pd.DataFrame(
    validation_rows
)
~~~

Now all individual validation dictionaries become one table.

Pipeline also calculates:

~~~python
summary_frame = monthly_summary(
    transaction_frame
)
~~~

---

# 97. Pipeline asks final safety gate

Code:

~~~python
safe, reasons = export_is_safe(
    validation_frame,
    uploaded_file_count=len(files),
    parsed_file_count=len(parsed_files),
)
~~~

Open:

~~~text
src/consolidated_state/readiness.py
~~~

---

# 98. File 13 — readiness.py

Blocking statuses:

~~~python
BLOCKING_STATUSES = {
    "ERROR",
    "TOO_LARGE",
    "PASSWORD_REQUIRED",
    "OCR_REQUIRED",
    "INVALID_PDF",
    "DUPLICATE_FILE",
    "NEEDS_BANK_PARSER",
    "NEEDS_LAYOUT_STRATEGY",
    "FAIL",
    "NEEDS_REVIEW",
}
~~~

Core question:

~~~text
Did every uploaded file parse?
AND
are there zero blocking validation rows?
~~~

If yes:

~~~text
safe = True
~~~

Otherwise:

~~~text
safe = False
reasons = [...]
~~~

This is the final gate before report creation.

---

# 99. Back to pipeline.py — totals

Pipeline selects credits:

~~~python
credits = transaction_frame[
    transaction_frame[
        "credit"
    ].notna()
]
~~~

and debits:

~~~python
debits = transaction_frame[
    transaction_frame[
        "debit"
    ].notna()
]
~~~

Then sum_money() calculates totals.

sum_money lives in:

~~~text
report_data.py
~~~

The next section below explains it.

---

# 100. File 14 — report_data.py

sum_money():

~~~python
def sum_money(
    series: pd.Series
) -> Decimal:
    total = Decimal("0.00")

    for value in series:
        if value is None or pd.isna(value):
            continue

        total += (
            value
            if isinstance(
                value,
                Decimal
            )
            else Decimal(
                str(value)
            )
        )

    return total
~~~

Purpose:

Accumulate financial totals using Decimal.

---

# 101. build_statement_frame()

Input:

~~~text
list[StatementSummary]
~~~

Output:

~~~text
pandas DataFrame
~~~

One row per source statement:

~~~text
source_file
statement_period
currency
account_identifier_detected
opening_balance
closing_balance
layout_strategy
~~~

This is used both by pipeline and report exporters.

---

# 102. build_overview_frame()

Calculates:

~~~text
covered period
currency
source statement count
transaction count
credit count
credit total
debit count
debit total
net change
beginning balance
ending balance
~~~

It creates a two-column DataFrame:

~~~text
Metric | Value
~~~

Now return to pipeline.py.

---

# 103. Pipeline only exports if safe

Code:

~~~python
excel_report = None
pdf_report = None

if safe:
    excel_report = build_excel_report(
        transaction_frame,
        summary_frame,
        validation_frame,
        statement_summaries,
    )

    pdf_report = build_pdf_report(
        transaction_frame,
        summary_frame,
        validation_frame,
        statement_summaries,
    )
~~~

This is extremely important.

Unsafe result:

~~~text
no Excel
no PDF
~~~

Safe result:

~~~text
generate both
~~~

---

# 104. File 15 — export_excel.py

Entry point:

~~~python
def build_excel_report(
    transactions: pd.DataFrame,
    summary: pd.DataFrame,
    validation: pd.DataFrame,
    statements: list[StatementSummary] | None = None,
) -> bytes:
~~~

Return type:

~~~text
bytes
~~~

not a saved filesystem path.

---

# 105. Excel in-memory buffer

Code:

~~~python
buffer = BytesIO()
~~~

Think:

~~~text
an in-memory file-like object
~~~

Then:

~~~python
with pd.ExcelWriter(
    buffer,
    engine="openpyxl"
) as writer:
~~~

pandas/openpyxl write the workbook into memory.

---

# 106. Excel sheets

Important calls:

~~~python
build_overview_frame(
    transactions,
    statements
).to_excel(
    writer,
    sheet_name="Overview",
    index=False
)
~~~

and similarly:

~~~text
Source Statements
Credits & Deposits
Debits & Withdrawals
All Transactions
Monthly Summary
Validation
About
~~~

Then workbook formatting is applied.

Finally:

~~~python
return buffer.getvalue()
~~~

This returns Excel binary bytes.

No permanent server file is required.

Return to pipeline.py.

---

# 107. File 16 — export_pdf.py

Entry point:

~~~python
def build_pdf_report(
    transactions: pd.DataFrame,
    summary: pd.DataFrame,
    validation: pd.DataFrame,
    statements: list[StatementSummary] | None = None,
) -> bytes:
~~~

Again:

~~~text
returns bytes
~~~

---

# 108. PDF in-memory buffer

Code:

~~~python
buffer = BytesIO()
~~~

Then ReportLab:

~~~python
doc = SimpleDocTemplate(
    buffer,
    pagesize=landscape(letter),
    ...
)
~~~

Everything is built into that memory buffer.

---

# 109. PDF story

Code:

~~~python
story: list[object] = []
~~~

ReportLab builds a document from flowable objects such as:

~~~text
Paragraph
Spacer
Table
PageBreak
~~~

The code repeatedly:

~~~python
story.append(...)
~~~

Then:

~~~python
doc.build(
    story,
    onFirstPage=_footer,
    onLaterPages=_footer,
)
~~~

Finally:

~~~python
return buffer.getvalue()
~~~

Now pipeline.py has:

~~~text
excel_report bytes
pdf_report bytes
~~~

---

# 110. Pipeline's final return

It creates:

~~~python
return ConsolidationResult(
    inspections=inspection_frame,
    statements=statement_frame,
    transactions=transaction_frame,
    monthly_summary=summary_frame,
    validation=validation_frame,
    safe_to_export=safe,
    blocking_reasons=reasons,
    excel_report=excel_report,
    pdf_report=pdf_report,
    total_credits=total_credits,
    total_debits=total_debits,
)
~~~

process_statements() is now over.

Control returns to app.py.

---

# 111. File 17 — back to app.py

Recall:

~~~python
st.session_state[
    "consolidation_result"
] = process_statements(
    inputs
)
~~~

The return value is now stored in Streamlit session state.

Then later:

~~~python
result = st.session_state.get(
    "consolidation_result"
)

if isinstance(
    result,
    ConsolidationResult
):
    render_result(result)
~~~

So browser rendering begins.

---

# 112. render_result()

Important metrics:

~~~python
len(result.statements)
len(result.transactions)
result.total_credits
result.total_debits
result.net_change
~~~

These came from pipeline's ConsolidationResult.

No PDF parsing happens here.

The frontend is only displaying results.

---

# 113. Tabs

app.py creates tabs:

~~~text
Overview
Source statements
Transactions
Monthly summary
Validation
~~~

Each tab displays a DataFrame from ConsolidationResult.

Example:

~~~python
st.dataframe(
    result.transactions,
    ...
)
~~~

This is presentation, not parsing.

---

# 114. Download buttons

If:

~~~python
result.safe_to_export
~~~

is False:

~~~python
return
~~~

so download buttons are not shown.

If safe:

~~~python
st.download_button(
    "Download Excel workbook",
    data=result.excel_report,
    ...
)
~~~

and:

~~~python
st.download_button(
    "Download PDF report",
    data=result.pdf_report,
    ...
)
~~~

Those bytes were built in the exporter modules.

---

# 115. Where data lives through the whole process

Trace one uploaded PDF:

~~~text
Browser
    ↓
Streamlit UploadedFile
    ↓
uploaded.getvalue()
    ↓
pdf_bytes
    ↓
pipeline local variable
    ↓
PyMuPDF Document
    ↓
plain text string
    ↓
DocumentLayout
    ↓
Transaction objects
    ↓
pandas DataFrame
    ↓
ConsolidationResult
    ↓
Streamlit session_state
~~~

Generated outputs:

~~~text
DataFrames
    ↓
BytesIO
    ↓
Excel/PDF bytes
    ↓
ConsolidationResult
    ↓
download button
~~~

Our code does not intentionally write the uploaded statement PDFs to a persistent project file or database.

---

# 116. The import graph versus the execution graph

These are different ideas.

Import graph means:

~~~text
Which file needs names from which other file?
~~~

Example:

~~~text
pipeline.py
    imports parse_statement
    from parser.py
~~~

Execution graph means:

~~~text
Which function is actually called at runtime?
~~~

Example:

~~~text
app.py
    process_statements()
        ↓
pipeline.py
    parse_statement()
        ↓
parser.py
~~~

Imports make functions/classes available.

Calls actually execute them.

This distinction is important.

---

# 117. "I see a function defined but when does it run?"

Definition:

~~~python
def parse_statement(...):
    ...
~~~

does not process a statement immediately.

It creates a function object.

It runs only when another line calls:

~~~python
parse_statement(...)
~~~

Same with classes:

~~~python
class LedgerColumnsStrategy:
    ...
~~~

defines a class.

Then:

~~~python
LedgerColumnsStrategy()
~~~

creates an instance.

Then:

~~~python
parser.matches(layout)
~~~

calls a method.

Then maybe:

~~~python
parser.parse(...)
~~~

calls another method.

---

# 118. Call stack for one ledger statement

Use this as a concrete trace:

~~~text
app.py
    process_statements(inputs)

pipeline.py
    for source_file, pdf_bytes in files

pipeline.py
    inspect_and_extract_pdf(...)

pdf_inspect.py
    fitz.open(...)
    page.get_text("text")
    return PdfInspection, text

pipeline.py
    parse_statement(...)

parser.py
    extract_document_layout(...)

layout.py
    fitz.open(...)
    page.get_text("words")
    _group_words_into_rows(...)
    return DocumentLayout

parser.py
    LedgerColumnsStrategy.matches(layout)

generic_parsers.py
    _ledger_header_columns(...)
    _concept_span(...)
    return True

parser.py
    LedgerColumnsStrategy.parse(...)

generic_parsers.py
    infer date order
    find table header
    calculate X boundaries
    loop transaction rows
    money_from_words(...)
    create Transaction(...)
    return ParseResult

parser.py
    extract_statement_metadata(...)

metadata.py
    find period
    find account fingerprint
    find currency
    return StatementMetadata

parser.py
    _enrich_result(...)
    return ParseResult

pipeline.py
    extend all_transactions
    append statement summary

... repeat for other PDFs ...

pipeline.py
    transactions_to_frame(...)

consolidate.py
    return DataFrame

pipeline.py
    validate...

validate.py
    return validation rows

pipeline.py
    export_is_safe(...)

readiness.py
    return safe, reasons

pipeline.py
    build_excel_report(...)
    build_pdf_report(...)

pipeline.py
    return ConsolidationResult

app.py
    render_result(...)
~~~

This is the exact "hopping" map.

---

# 119. Which helper should you ignore until called?

When first reading generic_parsers.py, do NOT try to memorize every helper.

If you are tracing LedgerColumnsStrategy, only follow helpers it calls:

~~~text
infer_numeric_date_order
_ledger_header_columns
_concept_span
_header_alias_matches
parse_date
money_from_words
find_labeled_balance
statement_period
~~~

Ignore SectionedAmountStrategy until later.

Then trace SignedAmountBalanceStrategy separately.

Then trace SectionedAmountStrategy separately.

This prevents cognitive overload.

---

# 120. How to annotate the repository while reading

For every function, write three notes:

~~~text
INPUT:
OUTPUT:
CALLED BY:
~~~

Example:

~~~text
inspect_and_extract_pdf

INPUT:
    pdf_bytes
    source_file

OUTPUT:
    PdfInspection
    text string

CALLED BY:
    process_statements()
~~~

Example:

~~~text
extract_document_layout

INPUT:
    pdf_bytes

OUTPUT:
    DocumentLayout

CALLED BY:
    parse_statement()
~~~

Example:

~~~text
LedgerColumnsStrategy.parse

INPUT:
    DocumentLayout
    source_file

OUTPUT:
    ParseResult

CALLED BY:
    parse_statement()
~~~

This simple habit makes jumping between files much easier.

---

# 121. Function ownership map

Use this reference.

| Function/Class | File | Called mainly by |
|---|---|---|
| passcode_matches | access.py | app.py |
| process_statements | pipeline.py | app.py |
| inspect_and_extract_pdf | pdf_inspect.py | pipeline.py |
| extract_document_layout | layout.py | parser.py |
| extract_statement_metadata | metadata.py | parser.py / date inference |
| parse_statement | parser.py | pipeline.py |
| LedgerColumnsStrategy | generic_parsers.py | parser.py registry |
| SignedAmountBalanceStrategy | generic_parsers.py | parser.py registry |
| SectionedAmountStrategy | generic_parsers.py | parser.py registry |
| transactions_to_frame | consolidate.py | pipeline.py |
| find_duplicate_transactions | consolidate.py | pipeline.py |
| monthly_summary | consolidate.py | pipeline.py |
| validate_transaction_rows | validate.py | pipeline.py |
| validate_statement_set | validate.py | pipeline.py |
| reconcile_statement | validate.py | pipeline.py |
| export_is_safe | readiness.py | pipeline.py |
| build_statement_frame | report_data.py | pipeline.py / exporters |
| build_overview_frame | report_data.py | exporters |
| build_excel_report | export_excel.py | pipeline.py |
| build_pdf_report | export_pdf.py | pipeline.py |
| render_result | app.py | app.py |

---

# 122. Data-shape map

Also remember what each stage works with.

~~~text
app.py
    UploadedFile objects

↓ getvalue()

pipeline.py
    list[(filename, bytes)]

↓ inspect

pdf_inspect.py
    bytes
    → PdfInspection + str

↓ geometry

layout.py
    bytes
    → DocumentLayout

↓ parse

generic_parsers.py
    DocumentLayout
    → ParseResult

↓ consolidate

consolidate.py
    list[Transaction]
    → DataFrame

↓ validate

validate.py
    DataFrame + StatementSummary list
    → dictionaries / validation rows

↓ export

exporters
    DataFrames
    → bytes

↓ frontend

app.py
    ConsolidationResult
    → browser UI
~~~

---

# 123. Why there are two different "rows"

This can be confusing.

Layout row:

~~~text
LayoutRow
~~~

represents a visual line from the PDF.

Pandas row:

~~~text
one row in transaction_frame
~~~

represents a normalized transaction record.

These are not the same thing.

PDF LayoutRow might be:

~~~text
"01/14/26 Coffee 5.00 1095.00"
~~~

Parser converts it into Transaction.

Then Transaction becomes pandas row:

~~~text
date=2026-01-14
description=Coffee
debit=5.00
credit=None
balance=1095.00
~~~

---

# 124. Why metadata scanning happens after transaction parsing

The architecture could technically scan metadata earlier.

Current parser flow is:

~~~text
layout
    ↓
strategy parse
    ↓
ParseResult
    ↓
_enrich_result()
    ↓
metadata scan
~~~

Why this still works:

Both transaction parser and metadata parser use the same DocumentLayout.

Transaction strategy determines:

~~~text
what financial table structure exists
~~~

Metadata adds:

~~~text
period
currency
account fingerprint
~~~

Then final ParseResult contains both.

---

# 125. Why text is passed to parse_statement if it is deleted

Current flow evolved from an earlier text-first parser design.

Now:

~~~python
del text
~~~

because transaction strategies use layout geometry.

The plain string is still useful in PDF pre-flight to distinguish:

~~~text
embedded-text PDF
vs
likely scanned PDF
~~~

So the current architecture has both:

~~~text
plain text detection
and
geometric word parsing
~~~

---

# 126. Why this is not an AI agent

Nothing in this execution chain asks an LLM:

~~~text
"What do you think this transaction means?"
~~~

The automation is rule-based:

~~~text
extract
locate
match
normalize
calculate
validate
export
~~~

That is still a real automation tool.

It just is not generative AI.

---

# 127. The three strategy mental models

LedgerColumnsStrategy:

~~~text
separate debit and credit columns
~~~

SignedAmountBalanceStrategy:

~~~text
one amount column
direction proven by sign / CR-DR / balance movement
~~~

SectionedAmountStrategy:

~~~text
one amount column
direction comes from current section heading
~~~

That is the main conceptual difference between the three.

---

# 128. When a new bank arrives

Do not think:

~~~text
"Add Bank XYZ parser."
~~~

Think:

~~~text
1. Extract DocumentLayout.
2. Do existing strategy.matches() methods recognize structure?
3. If yes:
       use existing parser.
4. If no:
       identify new reusable layout family.
5. Add another strategy.
~~~

This is how the software remains bank-agnostic.

---

# 129. What tests do

tests/ does not participate in normal user processing.

It runs separately when we execute:

~~~bash
pytest -q
~~~

Tests create controlled inputs and assert expected outputs.

Example concept:

~~~text
synthetic PDF
    ↓
parse_statement()
    ↓
expect:
    2 transactions
    correct debit
    correct credit
~~~

Tests are development safety checks.

They are not part of the website request path.

---

# 130. Final reading plan — one sitting at a time

Do not try to read all files in one sitting.

## Sitting 1 — understand data and startup

Read:

~~~text
.replit
.streamlit/config.toml
models.py
app.py upload block
~~~

Goal:

Understand how browser input becomes bytes.

## Sitting 2 — understand PDF extraction

Read:

~~~text
pipeline.py first half
pdf_inspect.py
layout.py
~~~

Goal:

Understand bytes → text / geometry.

## Sitting 3 — understand parser selection

Read:

~~~text
parser.py
metadata.py entry point
~~~

Goal:

Understand DocumentLayout → chosen strategy.

## Sitting 4 — understand ONE parser only

Read:

~~~text
generic_parsers.py
LedgerColumnsStrategy only
~~~

Goal:

Understand header detection + X boundaries + Transaction creation.

Do not read other strategies yet.

## Sitting 5 — understand other parser families

Read:

~~~text
SignedAmountBalanceStrategy
SectionedAmountStrategy
~~~

Goal:

Understand why direction logic differs.

## Sitting 6 — understand consolidation and validation

Read:

~~~text
consolidate.py
validate.py
readiness.py
~~~

Goal:

Understand how normalized transactions become trusted output.

## Sitting 7 — understand report generation

Read:

~~~text
report_data.py
export_excel.py
export_pdf.py
~~~

Goal:

Understand DataFrames → report bytes.

## Sitting 8 — return to app.py

Read:

~~~text
render_result()
download buttons
~~~

Goal:

Understand how backend results become browser output.

---

# 131. One final start-to-finish story

Imagine dad uploads January.pdf.

1. Replit is already running:

~~~text
streamlit run app.py
~~~

2. app.py receives UploadedFile.

3. getvalue() produces:

~~~text
pdf_bytes
~~~

4. app.py calls:

~~~text
process_statements
~~~

5. pipeline.py loops over January.pdf.

6. pdf_inspect.py:
   - hashes bytes;
   - checks size;
   - opens PDF with PyMuPDF;
   - checks password;
   - gets flat text;
   - returns TEXT_READY.

7. pipeline.py calls parse_statement().

8. parser.py calls layout.py.

9. layout.py:
   - opens bytes with PyMuPDF;
   - calls get_text("words");
   - converts raw word tuples into LayoutWord;
   - groups words by Y into LayoutRow;
   - returns DocumentLayout.

10. parser.py asks LedgerColumnsStrategy.matches().

11. generic_parsers.py finds a compatible header.

12. LedgerColumnsStrategy.parse():
   - identifies header positions;
   - computes debit/credit/balance boundaries;
   - loops table rows;
   - recognizes dates;
   - extracts description-region words;
   - extracts money-region words;
   - builds Transaction objects.

13. parser.py enriches ParseResult with metadata.

14. pipeline.py collects transactions.

15. consolidate.py builds one DataFrame.

16. validate.py checks:
   - transaction structure;
   - account/currency compatibility;
   - date continuity;
   - balance reconciliation.

17. readiness.py decides whether export is safe.

18. report_data.py builds shared summaries.

19. export_excel.py creates workbook bytes.

20. export_pdf.py creates report bytes.

21. pipeline.py returns ConsolidationResult.

22. app.py stores it in Streamlit session state.

23. render_result() displays:
   - metrics;
   - tables;
   - validation;
   - download buttons.

That is the whole application.

---

# 132. The sentence to use whenever you get lost

Ask:

> "What object do I have right now, and which function receives it next?"

Examples:

~~~text
I have pdf_bytes.
Who gets it next?
    inspect_and_extract_pdf.

I have DocumentLayout.
Who gets it next?
    strategy.matches / strategy.parse.

I have list[Transaction].
Who gets it next?
    transactions_to_frame.

I have DataFrames.
Who gets them next?
    validation and exporters.

I have ConsolidationResult.
Who gets it next?
    render_result.
~~~

If you keep track of the current object, the jumping between files becomes much easier.

---

# 133. Minimal code map to memorize

You do not need to memorize the entire repository.

Memorize only this:

~~~text
app.py
    ↓
pipeline.py
    ↓
pdf_inspect.py
    ↓
parser.py
    ↓
layout.py
    ↓
generic_parsers.py
    ↓
metadata.py
    ↓
consolidate.py
    ↓
validate.py
    ↓
readiness.py
    ↓
report_data.py
    ↓
export_excel.py / export_pdf.py
    ↓
app.py
~~~

The exact runtime jumps slightly back and forth, but this is the conceptual path.

---

# 134. Which three files matter most?

If you can only study three:

## pipeline.py

Answers:

> "What happens from beginning to end?"

## layout.py

Answers:

> "How does the PDF become structured data?"

## generic_parsers.py

Answers:

> "How does structured PDF data become transactions?"

Everything else either supports, validates, exports, or displays those results.

---

# 135. Final mental model

The repository is not many unrelated files.

It is one pipeline split across files:

~~~text
INPUT
  app.py

ORCHESTRATION
  pipeline.py

RAW PDF CHECK
  pdf_inspect.py

PDF STRUCTURE
  layout.py

PARSER ROUTING
  parser.py

STATEMENT METADATA
  metadata.py

TRANSACTION EXTRACTION
  generic_parsers.py

TABLE BUILDING
  consolidate.py

CORRECTNESS
  validate.py

FINAL SAFETY GATE
  readiness.py

REPORT DATA
  report_data.py

OUTPUT FILES
  export_excel.py
  export_pdf.py

DISPLAY
  app.py
~~~

When you see a function call into another file, it is not random hopping.

It is one stage handing an object to the next stage.


---

# Self-contained reading rule for the remaining sections

Whenever an older sentence in this document says something similar to "return to pipeline.py" or names the next file, interpret it as:

> Continue to the next section in THIS Markdown document.

The file name tells you which source module the shown code belongs to. You do not need to open that module separately.

The important source excerpts required to understand the execution path are included here. The only code intentionally not reproduced in full is code that does not materially change the program flow, such as large CSS styling blocks, repetitive Excel column formatting, repetitive ReportLab visual formatting, and automated-test fixture setup.

Those omitted pieces affect appearance or testing, not the core question:

~~~text
How does an uploaded bank-statement PDF
become a validated consolidated report?
~~~
