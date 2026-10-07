
# CODE WALKTHROUGH — From Uploaded PDF to Consolidated Report

This is the second learning guide for ConsolidatedState.

The first guide, UNDERSTANDING_THE_PROJECT.md, explains the product and architecture.

This guide explains the CODE itself in much greater depth.

The goal is not for you to memorize every line. The goal is for you to be able to look at the Python files and understand:

- what executes first;
- where the uploaded PDF exists;
- where PDF text comes from;
- why we extract the PDF twice in two different forms;
- what X/Y geometry means;
- what nested lists, dictionaries, tuples, sets, classes, and comprehensions mean;
- how metadata.py searches rows;
- what regular-expression group(1), group(2), and group(3) mean;
- how parser.py chooses a strategy;
- what LedgerColumnsStrategy.matches() and LedgerColumnsStrategy.parse() actually do;
- how transactions are stored;
- how validation works;
- where data is temporary;
- how the whole program becomes an automation tool.

Read this file slowly. You do not need to understand generic_parsers.py before understanding the earlier sections.

---

# 1. The single most important idea

The PDF is NOT simply converted into one text string and then searched line-by-line for everything.

We actually use two views of the same PDF.

View A is plain text:

    PDF bytes
        ↓
    PyMuPDF
        ↓
    page.get_text("text")
        ↓
    one large Python string

This is currently used mainly during PDF pre-flight to determine whether usable embedded text exists.

View B is geometric word data:

    same PDF bytes
        ↓
    PyMuPDF
        ↓
    page.get_text("words")
        ↓
    every word PLUS coordinates
        ↓
    rows reconstructed
        ↓
    layout strategies

View B is what the transaction parsers primarily use.

That distinction explains a lot of the code.

---

# 2. Exact call path from the browser

The important execution chain is:

    app.py
        ↓
    uploaded.getvalue()
        ↓
    PDF becomes Python bytes
        ↓
    process_statements(...) in pipeline.py
        ↓
    inspect_and_extract_pdf(...) in pdf_inspect.py
        ↓
    plain embedded text check
        ↓
    parse_statement(...) in parser.py
        ↓
    extract_document_layout(...) in layout.py
        ↓
    page.get_text("words")
        ↓
    DocumentLayout
        ↓
    strategy.matches(...)
        ↓
    strategy.parse(...)
        ↓
    Transaction objects
        ↓
    pandas DataFrame
        ↓
    validation
        ↓
    Excel/PDF report bytes
        ↓
    Streamlit download button

We will walk through this exact chain.

---

# 3. Python syntax first: from __future__ import annotations

You saw this line in many files:

    from __future__ import annotations

This is a Python language feature.

It mainly affects TYPE ANNOTATIONS.

For example:

    def sha256_bytes(data: bytes) -> str:

The annotations say:

    data should be bytes
    return value should be str

Another example:

    def inspect_and_extract_pdf(
        pdf_bytes: bytes,
        source_file: str
    ) -> tuple[PdfInspection, str]:

That says:

    input 1 = bytes
    input 2 = string

    return =
        tuple containing:
            item 1 = PdfInspection
            item 2 = string

The future import makes Python postpone evaluation of annotations.

For learning purposes, think of it as:

    "Treat the type hints mainly as descriptions of expected shapes."

It does NOT extract PDFs.
It does NOT run the parser.
It does NOT change the bank logic.

---

# 4. What are bytes?

When a PDF is uploaded, Python does not immediately see:

    Date
    Description
    Amount

A PDF file is initially just binary data.

In app.py we have:

    inputs = [
        (uploaded.name, uploaded.getvalue())
        for uploaded in uploaded_files
    ]

uploaded.getvalue() returns the actual uploaded file contents as bytes.

Conceptually:

    uploaded.name
        =
    "September.pdf"

and:

    uploaded.getvalue()
        =
    b"%PDF-1.7 ... lots of binary data ..."

The leading b means it is a bytes object rather than a normal text string.

So an input pair looks conceptually like:

    (
        "September.pdf",
        b"%PDF ... binary contents ..."
    )

The application can hold several of these pairs in a list.

---

# 5. Understanding a nested type: list[tuple[str, bytes]]

pipeline.py receives:

    files: list[tuple[str, bytes]]

Read from the inside outward.

First:

    tuple[str, bytes]

means one pair:

    (
        filename string,
        PDF byte data
    )

Example:

    (
        "August.pdf",
        b"...PDF bytes..."
    )

Then:

    list[tuple[str, bytes]]

means a LIST containing many of those pairs.

Example:

    [
        ("August.pdf", b"..."),
        ("September.pdf", b"..."),
        ("October.pdf", b"..."),
    ]

Nothing magical is happening.

It is simply:

    list
        item 0 = tuple
        item 1 = tuple
        item 2 = tuple

---

# 6. Lists, tuples, dictionaries, and sets

These appear everywhere.

## List

Example:

    transactions = []

or typed:

    transactions: list[Transaction] = []

A list is ordered and mutable.

You can append:

    transactions.append(transaction)

Example value:

    [
        Transaction(...),
        Transaction(...),
        Transaction(...),
    ]

## Tuple

Example:

    ("August.pdf", pdf_bytes)

A tuple is an ordered group of values that we generally do not mutate.

Another tuple type:

    tuple[PdfInspection, str]

means:

    (
        PdfInspection object,
        text string
    )

## Dictionary

Example:

    {
        "source_file": "August.pdf",
        "status": "PASS",
        "detail": "Parsed correctly"
    }

A dictionary maps keys to values.

You access:

    row["status"]

which gives:

    "PASS"

## Set

Example:

    known_currencies = {
        "USD",
        "USD",
        "USD",
    }

A set keeps unique values, so that becomes:

    {"USD"}

If it becomes:

    {"USD", "PKR"}

then:

    len(known_currencies) == 2

which tells us multiple currencies were detected.

---

# 7. A confusing type: list[dict[str, object]]

pipeline.py uses things like:

    validation_rows: list[dict[str, object]] = []

Break it apart.

Inside:

    dict[str, object]

means one dictionary whose keys are strings.

For example:

    {
        "source_file": "August.pdf",
        "check": "parser",
        "status": "PASS",
        "detail": "Parsed successfully",
        "difference": None,
    }

The values are different types:

    string
    string
    string
    string
    None

So the annotation uses object as a broad type.

Then:

    list[dict[str, object]]

means many such dictionaries:

    [
        {
            "source_file": "August.pdf",
            "check": "pdf_intake",
            "status": "PASS",
        },
        {
            "source_file": "August.pdf",
            "check": "parser",
            "status": "PASS",
        },
    ]

This is why it can look like a "dictionary inside a list."

That is exactly what it is.

---

# 8. app.py: where the upload begins

The Streamlit widget is:

    uploaded_files = st.file_uploader(
        "Upload bank statement PDFs",
        type=["pdf"],
        accept_multiple_files=True,
        ...
    )

If the user selects three files, uploaded_files behaves like a collection containing three Streamlit UploadedFile objects.

Later:

    inputs = [
        (uploaded.name, uploaded.getvalue())
        for uploaded in uploaded_files
    ]

This is a LIST COMPREHENSION.

The longer equivalent would be:

    inputs = []

    for uploaded in uploaded_files:
        pair = (
            uploaded.name,
            uploaded.getvalue()
        )
        inputs.append(pair)

Both versions create the same basic structure.

The short version:

    [
        expression
        for item in collection
    ]

is common Python syntax.

---

# 9. Where is the uploaded PDF stored?

At our application-code level:

    uploaded.getvalue()

gives us bytes.

Then we place those bytes in:

    inputs

Then process_statements(inputs) receives them.

We do NOT intentionally write:

    open("statement.pdf", "wb")

and we do NOT save the uploaded PDF into a database.

During processing, the important data lives in Python objects in the running server process.

Conceptually:

    Streamlit UploadedFile
        ↓
    bytes object
        ↓
    local Python variables
        ↓
    temporary parser/layout objects
        ↓
    transaction DataFrames
        ↓
    generated report bytes

There is an important nuance:

The application code intentionally avoids persistence, but a hosting/runtime platform can manage network buffers, process memory, temporary resources, logs, or infrastructure outside our Python code.

So the accurate statement is:

    "Our application does not intentionally persist the uploaded bank statements to its project filesystem or database."

Do not interpret that as a claim that no hosting layer anywhere ever buffers a byte.

---

# 10. pipeline.py: the main automation loop

The central loop begins:

    for source_file, pdf_bytes in files:

Suppose:

    files = [
        ("August.pdf", AUGUST_BYTES),
        ("September.pdf", SEPTEMBER_BYTES),
    ]

First loop:

    source_file = "August.pdf"
    pdf_bytes = AUGUST_BYTES

Second loop:

    source_file = "September.pdf"
    pdf_bytes = SEPTEMBER_BYTES

So yes: this is where we repeatedly process each uploaded statement.

Inside the loop:

    inspection, text = inspect_and_extract_pdf(
        pdf_bytes,
        source_file
    )

That function returns TWO values.

Python unpacks them:

    inspection = first returned item
    text = second returned item

---

# 11. Now the file you pasted: pdf_inspect.py

Current important code:

    import hashlib
    import fitz

    from .models import PdfInspection

    MAX_PDF_BYTES = 20 * 1024 * 1024

Let us go line by line.

---

# 12. import hashlib

hashlib is part of Python's standard library.

We use it for:

    SHA-256

Specifically:

    hashlib.sha256(data).hexdigest()

This creates a fingerprint for the entire PDF byte sequence.

If two files have exactly the same bytes, they have the same SHA-256 digest for practical duplicate-file detection.

This is how:

    August.pdf

and:

    Copy of August.pdf

can still be detected as exact duplicates even though their filenames differ.

---

# 13. import fitz

fitz is the Python import name used by PyMuPDF.

PyMuPDF is the external PDF library.

So when you see:

    fitz.open(...)

or:

    page.get_text(...)

those methods are coming from PyMuPDF.

WE did not define page.get_text().

PyMuPDF did.

Very important:

    fitz.open(...)
        returns a PyMuPDF Document object

Iterating the document gives:

    PyMuPDF Page objects

A Page object has methods such as:

    page.get_text("text")
    page.get_text("words")

That is where get_text comes from.

---

# 14. from .models import PdfInspection

The leading dot:

    .models

means:

    "models.py from the same Python package"

It imports the PdfInspection dataclass we created.

That class looks conceptually like:

    PdfInspection(
        source_file,
        sha256,
        size_bytes,
        page_count,
        encrypted,
        has_text,
        status,
        detail,
    )

So PdfInspection is just a structured container for the result of the pre-flight inspection.

---

# 15. MAX_PDF_BYTES = 20 * 1024 * 1024

Computers commonly measure:

    1 KiB = 1024 bytes

Approximately:

    1 MiB = 1024 * 1024 bytes

So:

    20 * 1024 * 1024

is approximately:

    20 MiB

The application rejects files larger than that configured MVP limit.

---

# 16. sha256_bytes()

Code:

    def sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

Break it apart.

    def

means define a function.

    sha256_bytes

is the function name.

    data: bytes

means the expected input is bytes.

    -> str

means the function returns a string.

Inside:

    hashlib.sha256(data)

creates the SHA-256 hash object.

Then:

    .hexdigest()

converts the result to readable hexadecimal text.

Example shape:

    "8c1f6d..."

---

# 17. inspect_and_extract_pdf() signature

Code:

    def inspect_and_extract_pdf(
        pdf_bytes: bytes,
        source_file: str
    ) -> tuple[PdfInspection, str]:

Input:

    pdf_bytes
        raw PDF bytes

    source_file
        filename such as "August.pdf"

Output:

    (
        PdfInspection(...),
        extracted_text_string
    )

So if successful:

    inspection, text = inspect_and_extract_pdf(...)

might become:

    inspection.status == "TEXT_READY"

and:

    text == "Statement Period ... Deposits ..."

---

# 18. digest and size

Code:

    digest = sha256_bytes(pdf_bytes)
    size_bytes = len(pdf_bytes)

digest stores the SHA-256 fingerprint.

len(pdf_bytes) tells us how many bytes the uploaded PDF contains.

Both values exist only as normal Python variables here.

---

# 19. Empty-file check

Code:

    if size_bytes == 0:
        return (
            PdfInspection(...),
            "",
        )

If the PDF contains zero bytes, there is nothing to parse.

The function immediately RETURNS.

Important Python idea:

Once return executes, that function invocation is over.

Nothing below it executes for that call.

---

# 20. File-size check

Code:

    if size_bytes > MAX_PDF_BYTES:
        return (...)

Again, if the file exceeds the configured limit, processing stops for that PDF.

The parser is never called for it.

---

# 21. try / except

Code shape:

    try:
        ...
    except Exception:
        ...

try means:

    "Attempt this code."

If a Python exception occurs inside the try block, execution jumps into except.

We intentionally convert a low-level PDF-reading failure into:

    status = "INVALID_PDF"

instead of crashing the whole application.

---

# 22. fitz.open(): turning bytes into a PDF Document object

The crucial line:

    with fitz.open(
        stream=pdf_bytes,
        filetype="pdf"
    ) as document:

This says:

    Take the PDF bytes in memory
    and let PyMuPDF interpret them as a PDF.

stream=pdf_bytes means we are opening bytes already in memory.

We are not saying:

    fitz.open("/some/path/statement.pdf")

The with statement is a context manager.

Conceptually:

    open document
        ↓
    use document
        ↓
    automatically close document

when leaving the block.

---

# 23. document.page_count

Code:

    page_count = document.page_count

PyMuPDF's Document object knows how many pages exist.

Example:

    4

That number goes into PdfInspection.

---

# 24. document.needs_pass

Code:

    if document.needs_pass:

This is asking PyMuPDF whether the document needs a password.

If yes, we return:

    PASSWORD_REQUIRED

and do not try to parse transactions.

---

# 25. THE EXACT LINE THAT EXTRACTS PLAIN TEXT

This is the line:

    text = "\n".join(
        page.get_text("text")
        for page in document
    )

This deserves careful attention.

First:

    for page in document

iterates through all PDF Page objects.

If the PDF has four pages, conceptually:

    page 1
    page 2
    page 3
    page 4

For each page:

    page.get_text("text")

asks PyMuPDF:

    "Give me this page's embedded text as ordinary text."

Conceptually:

    page 1 → "Statement information..."
    page 2 → "Account summary..."
    page 3 → "Deposits..."
    page 4 → "Withdrawals..."

This part:

    (
        page.get_text("text")
        for page in document
    )

is a generator expression.

It produces one text string per page.

Then:

    "\n".join(...)

joins them with newline characters.

Result:

    "PAGE 1 TEXT\nPAGE 2 TEXT\nPAGE 3 TEXT\nPAGE 4 TEXT"

That is the big flat text string.

---

# 26. Is this plain text used to parse every transaction?

This is the surprising answer:

CURRENTLY, mostly no.

Look at parser.py:

    def parse_statement(
        text: str,
        source_file: str,
        pdf_bytes: bytes | None = None,
    ) -> ParseResult:
        del text

That line:

    del text

explicitly discards the plain text parameter inside this function.

Why?

Because our transaction strategies rely on PDF geometry.

So why extract plain text at all?

Currently it is useful for the pre-flight question:

    "Does this PDF have embedded text?"

Code:

    has_text = bool(text.strip())

If text.strip() contains anything, has_text becomes True.

If the document is just scanned pictures with no embedded characters:

    text == ""

or effectively blank.

Then:

    OCR_REQUIRED

The actual transaction parser goes back to the PDF bytes and extracts WORDS WITH COORDINATES.

This is a major point to understand.

---

# 27. text.strip() and bool()

Code:

    has_text = bool(text.strip())

Suppose:

    text = "   \n   "

text.strip() removes surrounding whitespace.

Result:

    ""

bool("") is False.

But:

    text = "Bank Statement"

text.strip() remains:

    "Bank Statement"

bool("Bank Statement") is True.

So has_text answers:

    "Did PyMuPDF find non-whitespace embedded text?"

---

# 28. The return from pdf_inspect.py

Successful return:

    return (
        PdfInspection(...),
        text,
    )

Again, that is a tuple of TWO values.

Pipeline receives:

    inspection, text = ...

inspection tells us status and metadata.

text is the large plain string.

---

# 29. Where geometry begins: parser.py

Pipeline eventually calls:

    parsed = parse_statement(
        text,
        source_file,
        pdf_bytes=pdf_bytes,
    )

Then parser.py does:

    del text

and:

    layout = extract_document_layout(pdf_bytes)

So it uses the ORIGINAL PDF BYTES again.

This calls layout.py.

---

# 30. layout.py data classes

The smallest unit is:

    @dataclass(frozen=True)
    class LayoutWord:
        x0: float
        y0: float
        x1: float
        y1: float
        text: str

Imagine the word:

    Payroll

appears on the page.

PyMuPDF tells us something like:

    left x  = 150
    top y   = 220
    right x = 190
    bottom y = 232
    text = "Payroll"

We store it as:

    LayoutWord(
        x0=150,
        y0=220,
        x1=190,
        y1=232,
        text="Payroll"
    )

This means the word is not just text.

It is text WITH A LOCATION.

---

# 31. Understanding X and Y coordinates

Think of a PDF page like graph paper.

Top-left is approximately:

    x = 0
    y = 0

Moving right:

    x increases

Moving downward:

    y increases

Example:

    x=40                   x=400        x=500
      |                      |            |
      Date    Description    Debit        Balance
      01/02   Coffee         5.00         1095.00

Words on the same visual line have approximately the same Y coordinate.

Words in the same column have similar X regions.

This is how geometry helps recover tables.

---

# 32. LayoutWord.center_x

Code:

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

If a word spans:

    x0 = 400
    x1 = 430

then:

    center_x = 415

Later we use center_x to ask:

    "Is this monetary value inside the debit column,
     credit column,
     or balance column?"

---

# 33. What does @dataclass mean?

A dataclass lets us define data containers without writing a lot of boilerplate.

Instead of manually writing constructors, equality logic, etc., Python generates much of that behavior.

Example:

    @dataclass(frozen=True)
    class LayoutWord:
        x0: float
        ...
        text: str

lets us create:

    LayoutWord(
        x0=10,
        y0=20,
        x1=50,
        y1=30,
        text="Deposit"
    )

frozen=True means we treat the instance as immutable after creation.

---

# 34. LayoutRow

Code:

    class LayoutRow:
        y: float
        words: tuple[LayoutWord, ...]

The notation:

    tuple[LayoutWord, ...]

means:

    tuple containing zero or more LayoutWord objects

The ellipsis means the tuple can contain many of the same type.

Example:

    LayoutRow(
        y=100,
        words=(
            LayoutWord(..., text="01/02/26"),
            LayoutWord(..., text="Coffee"),
            LayoutWord(..., text="5.00"),
            LayoutWord(..., text="1095.00"),
        )
    )

---

# 35. LayoutRow.text

Code:

    return " ".join(
        word.text
        for word in self.words
    )

If words are:

    "Deposits"
    "and"
    "other"
    "additions"

row.text becomes:

    "Deposits and other additions"

This is convenient for regex/header matching.

---

# 36. PageLayout and DocumentLayout

PageLayout contains:

    page_number
    width
    height
    rows

DocumentLayout contains:

    pages

Conceptually:

    DocumentLayout
      ├── PageLayout 1
      │     ├── Row 1
      │     │    ├── Word
      │     │    └── Word
      │     └── Row 2
      │
      └── PageLayout 2
            ├── Row 1
            └── Row 2

This is one of the nested structures that looked intimidating.

But it is simply a hierarchy matching the PDF:

    document
      → pages
        → rows
          → words

---

# 37. THE EXACT GEOMETRY EXTRACTION LINE

In layout.py:

    rows=_group_words_into_rows(
        page.get_text("words")
    )

Here:

    page.get_text("words")

is again a PyMuPDF Page method.

But "words" is different from "text".

PyMuPDF returns word records similar in shape to:

    (
        x0,
        y0,
        x1,
        y1,
        "word text",
        block_number,
        line_number,
        word_number
    )

Our code mainly needs indexes:

    raw[0] = x0
    raw[1] = y0
    raw[2] = x1
    raw[3] = y1
    raw[4] = text

That is why you see:

    word = LayoutWord(
        float(raw[0]),
        float(raw[1]),
        float(raw[2]),
        float(raw[3]),
        str(raw[4]),
    )

We intentionally ignore later tuple items because we build our own row grouping.

---

# 38. Why raw[0], raw[1], raw[4]?

A tuple can be indexed by position.

Example:

    raw = (
        150.0,
        220.0,
        190.0,
        232.0,
        "Payroll",
        3,
        1,
        0
    )

Then:

    raw[0] → 150.0
    raw[1] → 220.0
    raw[2] → 190.0
    raw[3] → 232.0
    raw[4] → "Payroll"

Indexes begin at zero.

---

# 39. _group_words_into_rows()

This is the function that converts scattered words into visual rows.

Signature:

    def _group_words_into_rows(
        raw_words: list[tuple],
        tolerance: float = 2.2
    ) -> tuple[LayoutRow, ...]:

Input:

    many raw PyMuPDF word tuples

Output:

    tuple of LayoutRow objects

---

# 40. Sorting words top-to-bottom, then left-to-right

Code:

    ordered = sorted(
        raw_words,
        key=lambda word: (word[1], word[0])
    )

This key means:

    first sort by Y
    then sort by X

So words near the top appear first.

Within approximately the same Y area, words farther left appear before words farther right.

What is lambda?

This:

    lambda word: (word[1], word[0])

is a tiny unnamed function.

Long version:

    def sorting_key(word):
        return (
            word[1],
            word[0]
        )

Then:

    sorted(raw_words, key=sorting_key)

Same idea.

---

# 41. The nested structure working: list[dict[str, object]]

Code:

    working: list[dict[str, object]] = []

During row construction, it may temporarily look like:

    [
        {
            "y": 100.4,
            "words": [
                LayoutWord(text="Date", ...),
                LayoutWord(text="Description", ...),
                LayoutWord(text="Debit", ...),
            ]
        },
        {
            "y": 120.2,
            "words": [
                LayoutWord(text="01/01/26", ...),
                LayoutWord(text="Payroll", ...),
                LayoutWord(text="100.00", ...),
            ]
        }
    ]

So yes:

    list
        contains dictionaries

and each dictionary contains:

    "y" → float
    "words" → list of LayoutWord

This is temporary working data.

Later it becomes proper LayoutRow dataclasses.

---

# 42. Looping through each extracted word

Code:

    for raw in ordered:

Meaning:

    take one PyMuPDF word tuple at a time

Then:

    word = LayoutWord(...)

turn it into our cleaner object.

Next:

    matched = None

means:

    "We have not yet found a row for this word."

---

# 43. working[-8:]

Code:

    for row in working[-8:]:

Python slicing:

    working[-8:]

means:

    last eight items of working

Why?

The word list is already sorted by Y.

A new word is almost certainly near one of the most recently created visual rows.

We do not need to compare it against every row from the entire page.

---

# 44. The 2.2 tolerance

Code:

    if abs(
        float(row["y"]) - word.y0
    ) <= tolerance:

Suppose existing row Y:

    100.0

new word Y:

    101.1

Difference:

    abs(100.0 - 101.1)
    =
    1.1

Since:

    1.1 <= 2.2

we treat the word as belonging to the same visual row.

PDF text is not always perfectly aligned to the exact same decimal coordinate, so the tolerance allows slight differences.

---

# 45. matched = row and break

If we find a compatible row:

    matched = row
    break

break means:

    stop the current inner loop immediately

We already found the row.

There is no need to compare more.

---

# 46. If no row matched

Code:

    if matched is None:
        working.append({
            "y": word.y0,
            "words": [word]
        })

Create a new temporary row.

Notice:

    "words": [word]

That is a dictionary value containing a list.

At first the list has only one word.

---

# 47. If a row DID match

Code:

    words = matched["words"]

Get the list stored under:

    "words"

Then:

    words.append(word)

adds the new LayoutWord.

Then:

    matched["y"] = (
        float(matched["y"]) + word.y0
    ) / 2

This slightly updates the representative row Y coordinate.

---

# 48. Converting working dictionaries into LayoutRow objects

After all words are assigned:

    rows: list[LayoutRow] = []

Then:

    for row in working:

For each temporary dictionary:

    words = row["words"]

Then:

    words.sort(
        key=lambda word: word.x0
    )

Now words inside the row are ordered left-to-right.

Finally:

    rows.append(
        LayoutRow(
            y=float(row["y"]),
            words=tuple(words)
        )
    )

Notice:

    list → tuple

The temporary mutable list becomes an immutable tuple inside the dataclass.

---

# 49. extract_document_layout()

Core structure:

    pages: list[PageLayout] = []

    with fitz.open(...) as document:
        for page_number, page in enumerate(
            document,
            start=1
        ):
            pages.append(
                PageLayout(...)
            )

enumerate gives both:

    page_number
    page

start=1 means numbering begins at:

    1

instead of Python's usual zero.

Then:

    page.rect.width
    page.rect.height

come from PyMuPDF and describe page dimensions.

Finally:

    return DocumentLayout(
        pages=tuple(pages)
    )

At this point the PDF is represented in memory as:

    document
      pages
        rows
          words
            text + geometry

---

# 50. So are we looping through every word?

Yes.

But at different stages for different purposes.

Plain-text pre-flight:

    for page in document
        page.get_text("text")

Layout reconstruction:

    for page in document
        page.get_text("words")
            ↓
        for raw word
            ↓
        group into rows

Metadata scanning:

    for page in layout.pages
        for row in page.rows

Strategy matching:

    for page
        for row

Transaction parsing:

    for page
        find table header
        then scan rows after header

So yes, loops are central.

But we do not blindly ask:

    "Does this word equal deposit?"

for every word and immediately make a transaction.

We first recover STRUCTURE.

---

# 51. Capitalization: how "DEBIT", "Debit", and "debit" become equivalent

generic_parsers.py defines:

    def normalize(value: str) -> str:
        return re.sub(
            r"[^a-z0-9]+",
            "",
            value.lower()
        )

metadata.py has a similar private helper.

Take:

    "Running Balance"

First:

    value.lower()

becomes:

    "running balance"

Then regex removes characters that are not:

    a-z
    0-9

The space is removed.

Result:

    "runningbalance"

Examples:

    "DEBIT"
        → "debit"

    "Debit:"
        → "debit"

    "Money Out"
        → "moneyout"

    "Deposits & Other Additions"
        → "depositsotheradditions"

That is how capitalization and punctuation stop mattering for many header comparisons.

---

# 52. What is re?

Code:

    import re

re is Python's regular-expression module.

Regular expressions describe text patterns.

Simple example:

    r"\d+"

means:

    one or more digits

A raw string beginning with r is commonly used so backslashes are treated conveniently in regex patterns.

---

# 53. metadata.py: what is match.group(1)?

Consider:

    numeric = re.compile(
        r"^(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})$"
    )

The parentheses create CAPTURE GROUPS.

For:

    "13/01/2026"

the match contains approximately:

    group(0) = "13/01/2026"
    group(1) = "13"
    group(2) = "01"
    group(3) = "2026"

group(0) normally means the entire matched text.

group(1) means the first parenthesized capture.

group(2) means the second.

group(3) means the third.

That is why metadata.py can do:

    first_number = int(match.group(1))
    second_number = int(match.group(2))
    year_number = int(match.group(3))

---

# 54. re.compile(), fullmatch(), and search()

Three ideas:

## compile

    pattern = re.compile(...)

Build a reusable regex object.

## fullmatch

    pattern.fullmatch(text)

requires the ENTIRE text to fit the pattern.

If pattern is a date:

    "13/01/2026"
        → match

but:

    "Date: 13/01/2026"
        → not a full match

## search

    pattern.search(text)

looks ANYWHERE inside the string.

So:

    "Statement Period 13/01/2026 - 31/01/2026"

can be searched for a date-range pattern.

---

# 55. Metadata statement-period scanning

metadata.py has:

    for page in layout.pages:
        for row in page.rows:

So it visits every reconstructed row.

It asks questions such as:

    Does this row contain two token-style dates?
    Does it mention statement period?
    Does it contain a long date range?
    Does it contain a numeric range?

If it finds a convincing statement period, it returns it.

Example row:

    "Statement Period: From Date: 01-JAN-26 To Date 31-JAN-26"

The code extracts date-looking words.

---

# 56. A list comprehension in metadata.py

Code shape:

    token_dates = [
        parsed
        for word in row.words
        if (
            parsed := _parse_token_date(
                word.text
            )
        ) is not None
    ]

This is more advanced Python.

Longer equivalent:

    token_dates = []

    for word in row.words:
        parsed = _parse_token_date(
            word.text
        )

        if parsed is not None:
            token_dates.append(parsed)

The operator:

    :=

is called the walrus operator.

It assigns a value while evaluating an expression.

You do NOT need to use this syntax yourself to understand the project.

---

# 57. Account fingerprint scanning

metadata.py builds a regex for labels such as:

    Account Number:
    Account No:
    Account #
    Acct No:
    Account ending in ...

Then:

    for page in layout.pages[:3]:

means:

    only inspect the first three pages

because account-identification metadata normally appears near the beginning.

Then:

    for row in page.rows:
        match = label.search(row.text)

If there is no match:

    if not match:
        continue

continue means:

    skip the rest of THIS loop iteration
    and move to the next row

---

# 58. Why group(1) for the account identifier?

The regex contains one capture group around the candidate account text.

So:

    match.group(1)

returns the part after the label.

Example conceptual input:

    "Account ending in 4321"

Captured group:

    "4321"

Then the code cleans it and hashes it.

We keep:

    fingerprint

rather than showing the original account identifier in our report.

---

# 59. Currency scanning

Code concept:

    for page in layout.pages[:3]:
        for row in page.rows:

Then normalize row text.

If row does not include a currency label:

    continue

If it does, inspect each word.

Example:

    Currency: USD

Words might be:

    "Currency:"
    "USD"

Code strips punctuation and uppercases:

    "USD"

Then checks whether it exists in ISO_CURRENCIES.

---

# 60. models.py: where parsed information is stored

Our key dataclass:

    Transaction

contains:

    date
    description
    debit
    credit
    balance
    source_file
    statement_period

Example:

    Transaction(
        date=date(2026, 1, 14),
        description="COFFEE SHOP",
        debit=Decimal("5.00"),
        credit=None,
        balance=Decimal("1095.00"),
        source_file="January.pdf",
        statement_period="2026-01-01 to 2026-01-31"
    )

That is a NORMALIZED transaction.

The original bank could call the outgoing-money column:

    Debit
    Withdrawal
    Money Out

but internally we use:

    debit

---

# 61. Why Decimal instead of float?

A normal float is binary floating-point.

Financial calculations should avoid subtle binary representation errors.

So:

    Decimal("5.00")

represents decimal money intentionally.

The string:

    "5.00"

is converted to Decimal.

This is why money parsing eventually creates Decimal values.

---

# 62. parser.py: the part that confused you about classes

Current registry:

    PARSERS: list[ParserStrategy] = [
        LedgerColumnsStrategy(),
        SignedAmountBalanceStrategy(),
        SectionedAmountStrategy(),
    ]

This does NOT mean:

    "Run every definition inside every class right now."

It creates THREE OBJECTS.

Conceptually:

    parser_object_1 = LedgerColumnsStrategy()
    parser_object_2 = SignedAmountBalanceStrategy()
    parser_object_3 = SectionedAmountStrategy()

Then stores them:

    PARSERS = [
        parser_object_1,
        parser_object_2,
        parser_object_3
    ]

Methods execute only when called.

---

# 63. What is a class?

A class is a blueprint for objects.

Example simplified:

    class Dog:
        def bark(self):
            return "woof"

Creating:

    d = Dog()

does not automatically call:

    d.bark()

You must explicitly do:

    d.bark()

Same here.

Creating:

    LedgerColumnsStrategy()

does not automatically call:

    matches()
    parse()

Those happen later.

---

# 64. What is self?

Inside:

    class LedgerColumnsStrategy:
        def matches(self, layout):
            ...

self is the actual object receiving the method call.

When code says:

    parser.matches(layout)

and parser currently refers to the LedgerColumnsStrategy instance:

    self == parser

You can think of:

    parser.matches(layout)

as approximately:

    LedgerColumnsStrategy.matches(
        parser,
        layout
    )

Python handles self automatically.

---

# 65. What is @staticmethod?

LedgerColumnsStrategy contains:

    @staticmethod
    def header(row: LayoutRow) -> bool:
        ...

This method does not need access to:

    self

So it is marked static.

We can conceptually think of it as a helper function logically grouped inside the class.

---

# 66. ParserStrategy Protocol

parser.py contains:

    class ParserStrategy(Protocol):
        name: str

        def matches(...): ...
        def parse(...): ...

This mainly describes:

    "Any parser strategy object should provide:
        name
        matches()
        parse()"

It is useful for type checking and design clarity.

LedgerColumnsStrategy does not need to explicitly inherit from ParserStrategy for Python structural typing to recognize the shape.

For understanding runtime behavior, focus on:

    matches
    parse

---

# 67. Exact strategy-selection control flow

parse_statement() does:

    layout = extract_document_layout(
        pdf_bytes
    )

Then:

    for parser in PARSERS:

First parser object:

    LedgerColumnsStrategy instance

Call:

    parser.matches(layout)

If False:

    continue

Go to next parser object.

If True:

    parser.parse(
        layout,
        source_file
    )

Then:

    return ...

return means we STOP trying later strategies.

So the order matters.

Flow:

    LedgerColumnsStrategy.matches?
        ↓
      false
        ↓
    SignedAmountBalanceStrategy.matches?
        ↓
      false
        ↓
    SectionedAmountStrategy.matches?
        ↓
      true
        ↓
    SectionedAmountStrategy.parse()
        ↓
    return ParseResult

We do NOT parse the whole statement three times if the first strategy matches successfully.

---

# 68. What does matches() do?

matches() is a lightweight structural detector.

Example LedgerColumnsStrategy:

    def matches(self, layout):
        return any(
            self.header(row)
            for page in layout.pages
            for row in page.rows
        )

This is a nested generator expression.

Long form:

    for page in layout.pages:
        for row in page.rows:
            if self.header(row):
                return True

    return False

So it scans rows looking for a compatible header.

---

# 69. Understanding any(...)

any() returns True if at least one item is truthy.

Example:

    any([
        False,
        False,
        True,
        False
    ])

returns:

    True

So:

    any(
        self.header(row)
        for page ...
        for row ...
    )

means:

    "Does ANY row in ANY page look like the ledger header?"

---

# 70. Header aliases

We support concepts, not one exact bank wording.

Example sets:

    DEBIT_HEADERS = {
        "debit",
        "debits",
        "withdrawal",
        "withdrawals",
        "moneyout",
        "outflow",
        "paidout",
    }

    CREDIT_HEADERS = {
        "credit",
        "credits",
        "deposit",
        "deposits",
        "moneyin",
        "inflow",
        "additions",
    }

So:

    "Money Out"

normalizes to:

    "moneyout"

which can represent the debit concept.

This is one way we avoid hardcoding a bank name.

---

# 71. _concept_span(): finding a header concept in a row

Imagine header row words:

    Posting
    Date
    Description
    Money
    Out
    Money
    In
    Running
    Balance

Some concepts contain multiple words.

So _concept_span tries word groups of width:

    3
    2
    1

Example width 2:

    "Posting Date"
    "Money Out"
    "Money In"
    "Running Balance"

Each is normalized.

Then checked against alias sets.

If a concept is found, return:

    (
        left X coordinate,
        center X coordinate
    )

That geometry is later used to split table columns.

---

# 72. Why the fuzzy header matcher exists

PDF extraction can sometimes clip visible text.

Example visually:

    Running Balance

PyMuPDF might extract:

    Running Balanc

We therefore use a conservative near-match helper.

It first checks exact equality.

Then only for sufficiently long text it allows:

    strong prefix similarity

or:

    very high SequenceMatcher similarity

The goal is NOT broad fuzzy guessing.

It is to tolerate minor extraction defects.

---

# 73. _ledger_header_columns()

This function builds a dictionary such as:

    {
        "date": (40.0, 55.0),
        "debit": (390.0, 410.0),
        "credit": (465.0, 485.0),
        "balance": (535.0, 565.0),
    }

The exact numbers depend on the PDF.

Dictionary meaning:

    key
        conceptual column

    value
        (
            left coordinate,
            center coordinate
        )

Then:

    if any(value is None ...):
        return None

means:

    if a required column was not found,
    this row is not a valid ledger header

---

# 74. LedgerColumnsStrategy.matches()

Current conceptual logic:

    Scan all pages
        scan all rows
            does this row contain:
                date concept
                debit concept
                credit concept
                balance concept
            ?
                yes → True

It does not need to parse transactions yet.

It only needs to recognize the layout family.

---

# 75. LedgerColumnsStrategy.parse(): first step

Start:

    transactions = []
    date_order = infer_numeric_date_order(
        layout
    )

Then:

    for page in layout.pages:

For each page:

    header_index = None
    header = None
    columns = None

Then scan rows:

    for index, row in enumerate(
        page.rows
    ):

Try:

    detected = _ledger_header_columns(row)

When header found:

    header_index = index
    header = row
    columns = detected
    break

So now we know:

    where the table starts
    where debit is
    where credit is
    where balance is

---

# 76. Why boundaries are calculated

Suppose centers:

    debit center   = 410
    credit center  = 480
    balance center = 560

Then:

    debit_credit_boundary
        =
    (410 + 480) / 2
        =
    445

and:

    credit_balance_boundary
        =
    (480 + 560) / 2
        =
    520

So page regions become approximately:

    debit area:
        ... < center_x < 445

    credit area:
        445 <= center_x < 520

    balance area:
        center_x >= 520

This is geometry-based parsing.

---

# 77. Parsing one transaction row by coordinates

Imagine reconstructed row:

    01/14/26    COFFEE SHOP       5.00       1095.00

Each word has center_x.

The parser calculates:

    date_words

by finding words that parse as dates on the left side.

Debit amount:

    debit = money_from_words(
        [
            word
            for word in row.words
            if debit_left
               <= word.center_x
               < debit_credit_boundary
        ]
    )

That list comprehension means:

    Make a list containing only words whose center X lies inside the debit region.

Same for credit and balance.

Description is words between:

    detail_x

and:

    debit_left

So geometry defines the semantic columns.

---

# 78. Example geometry classification

Imagine:

    date:
        x = 40

    description:
        x = 150

    debit:
        x = 400

    credit:
        x = 470

    balance:
        x = 540

Row words:

    "01/14/26" center 65
    "Coffee"   center 175
    "5.00"     center 410
    "1095.00"  center 560

The parser sees:

    65
        date region

    175
        description region

    410
        debit region

    560
        balance region

and creates:

    Transaction(
        date=...,
        description="Coffee",
        debit=Decimal("5.00"),
        credit=None,
        balance=Decimal("1095.00")
    )

---

# 79. money_from_words()

Suppose amount words contain:

    ["1,095.00"]

Function does roughly:

    raw = "1,095.00"

Then:

    raw.replace(",", "")

becomes:

    "1095.00"

Regex removes non-numeric/non-period characters.

Then verifies:

    digits + decimal point + exactly two digits

Then:

    Decimal("1095.00")

So the numeric amount becomes a Decimal.

---

# 80. Multi-line descriptions

Some statements display:

    01/14/26   CARD PURCHASE...
               MERCHANT LOCATION...
               REFERENCE NUMBER...
               5.00    1095.00

Only the first row may contain the date.

Later rows may be description continuation.

LedgerColumnsStrategy tracks:

    current: Transaction | None

If a later row has no date but lies in description geometry:

    continuation = ...

Then rebuild:

    current = Transaction(
        current.date,
        current.description + continuation,
        ...
    )

That is how multi-line descriptions can be joined.

---

# 81. What does current: Transaction | None mean?

The variable can hold either:

    Transaction object

or:

    None

None means:

    "There is currently no transaction being accumulated."

The vertical bar:

    Transaction | None

is a union type annotation.

---

# 82. SectionedAmountStrategy

This handles statements like:

    Deposits and other additions

    Date       Description        Amount
    ...

    Withdrawals and other subtractions

    Date       Description        Amount
    ...

This parser does not need separate debit and credit columns.

Instead it tracks the CURRENT SECTION.

Variable:

    direction: str | None = None

Later:

    direction = "credit"

when a deposit/addition heading is detected.

Or:

    direction = "debit"

when a withdrawal/subtraction heading is detected.

---

# 83. section_direction()

It normalizes tokens.

Positive prefixes include:

    deposit
    addition
    credit
    income
    receipt

Negative prefixes include:

    withdraw
    subtract
    debit
    payment
    expense

So:

    "DEPOSITS & OTHER ADDITIONS"

contains normalized terms beginning with:

    deposit
    addition

and returns:

    "credit"

This is conceptual financial vocabulary, not a specific bank name.

---

# 84. Sectioned parser row logic

When it sees a section heading:

    direction = "credit"

Then later transaction row:

    01/13/26   Payroll   100.00

The parser gets:

    amount = Decimal("100.00")

Then:

    if direction == "credit":
        current = Transaction(
            ...,
            credit=abs(amount)
        )

If current direction were debit:

    debit=abs(amount)

That is how one Amount column is assigned to debit or credit based on section context.

---

# 85. SignedAmountBalanceStrategy

Third layout family:

    Date
    Description
    Amount
    Balance

Problem:

    Is Amount money in or money out?

We do not guess.

First try explicit markers:

    -100.00
    +100.00
    100.00 DR
    100.00 CR

If no explicit marker, use the running balance.

Example:

    previous balance = 1000
    amount = 100
    new balance = 1100

Delta:

    1100 - 1000 = +100

Therefore:

    credit

If:

    previous = 1100
    amount = 5
    new = 1095

Delta:

    -5

Therefore:

    debit

If amount and balance movement do not agree:

    raise GenericParseError

That is fail-closed behavior.

---

# 86. Date parsing and why it is complicated

Numeric date:

    01/02/26

could mean:

    January 2

or:

    1 February

So generic_parsers.py tries to infer order.

Unambiguous example:

    13/01/26

13 cannot be a month.

Therefore:

    DMY

Another:

    01/31/26

31 cannot be a month.

Therefore:

    MDY

If all dates are ambiguous, statement metadata can sometimes disambiguate them.

If the order cannot be proven:

    parse_date may return None

rather than guess.

---

# 87. What happens after a strategy parses?

It returns:

    ParseResult(
        transactions,
        StatementSummary(...),
        parser_name
    )

Then parser.py calls:

    _enrich_result(...)

This adds metadata discovered by metadata.py.

For example:

    exact statement period
    account fingerprint
    currency
    layout strategy name

It also updates every Transaction's statement_period.

---

# 88. dataclasses.replace()

parser.py uses:

    replace(
        result.statement,
        statement_period=period,
        ...
    )

Because our dataclasses use:

    frozen=True

we do not mutate the existing instance directly.

replace creates a NEW dataclass object based on the old one, changing selected fields.

---

# 89. How metadata and parsing are different

Transaction parser answers:

    "What transactions are in this table?"

Metadata parser answers:

    "What statement is this?"

Metadata examples:

    statement period
    currency
    account fingerprint

Transaction examples:

    date
    description
    debit
    credit
    balance

Those responsibilities are intentionally separate.

---

# 90. After parsing: list of Transaction objects

For two PDFs, we might have:

    all_transactions = [
        Transaction(...August row 1...),
        Transaction(...August row 2...),
        ...
        Transaction(...September row 1...),
        ...
    ]

pipeline.py does:

    all_transactions.extend(
        parsed.transactions
    )

Difference:

    append(list)

would add the whole list as one nested item.

    extend(list)

adds each transaction item individually.

Example:

    a = [1, 2]
    a.extend([3, 4])

result:

    [1, 2, 3, 4]

---

# 91. transactions_to_frame(): creating a pandas DataFrame

consolidate.py turns dataclasses into dictionaries:

    rows = [
        {
            "date": tx.date,
            "description": tx.description,
            "debit": tx.debit,
            ...
        }
        for tx in transactions
    ]

Imagine:

    rows = [
        {
            "date": Jan 1,
            "description": "Payroll",
            "debit": None,
            "credit": 100,
        },
        {
            "date": Jan 2,
            "description": "Coffee",
            "debit": 5,
            "credit": None,
        }
    ]

Then:

    pd.DataFrame(
        rows,
        columns=TRANSACTION_COLUMNS
    )

creates a table.

Conceptually:

    date       description    debit   credit
    Jan 1      Payroll        blank   100
    Jan 2      Coffee         5       blank

---

# 92. Where is the data stored at this point?

Still in server-process memory.

Important objects include:

    pdf_bytes
        bytes

    text
        string

    layout
        DocumentLayout object graph

    all_transactions
        Python list of Transaction objects

    transaction_frame
        pandas DataFrame

    validation_frame
        pandas DataFrame

    excel_report
        bytes

    pdf_report
        bytes

The code does not intentionally write these into a persistent database.

---

# 93. Validation: transaction integrity

validate_transaction_rows() loops:

    for _, row in frame.iterrows():

Each row is one normalized transaction.

Checks include:

    description exists
    source_file exists
    exactly one of debit/credit is present
    no negative normalized amount

Why exactly one side?

Valid:

    debit=5
    credit=None

Valid:

    debit=None
    credit=100

Suspicious:

    debit=5
    credit=100

Suspicious:

    debit=None
    credit=None

---

# 94. has_debit == has_credit

This compact condition confuses many people.

Possible cases:

    True == True
        both debit and credit exist
        invalid

    False == False
        neither exists
        invalid

So:

    if has_debit == has_credit:

means:

    "Either both sides are present or both sides are absent."

We want exactly one side.

---

# 95. Statement reconciliation

Core financial equation:

    expected_close
        =
    opening_balance
        +
    credits
        -
    debits

Then:

    difference
        =
    actual_closing_balance
        -
    expected_close

If:

    abs(difference) <= Decimal("0.01")

pass.

This is one of the strongest checks in the project.

---

# 96. Why abs()?

Suppose difference:

    -0.01

or:

    +0.01

We care about magnitude.

abs(-0.01) becomes:

    0.01

---

# 97. Cross-statement validation

validate_statement_set() receives:

    list[StatementSummary]

It uses set comprehensions such as:

    known_accounts = {
        statement.account_fingerprint
        for statement in statements
        if statement.account_fingerprint
    }

Long version:

    known_accounts = set()

    for statement in statements:
        if statement.account_fingerprint:
            known_accounts.add(
                statement.account_fingerprint
            )

If:

    len(known_accounts) > 1

then different detected accounts are present.

Same idea for explicit currencies.

---

# 98. zip(ordered, ordered[1:])

This is used for neighboring statement comparisons.

Suppose ordered is:

    [January, February, March]

Then:

    ordered[1:]

is:

    [February, March]

zip gives pairs:

    (January, February)
    (February, March)

So we can compare consecutive statement periods.

---

# 99. Statement overlap and gaps

If:

    current.statement_start
        <=
    previous.statement_end

there is overlap.

For gaps:

    gap_days
        =
    current.start - previous.end - 1 day

If gap_days > 0, some days are uncovered.

---

# 100. Balance continuity between months

If statements are adjacent and both balances exist:

    previous.closing_balance
        should match
    current.opening_balance

If not, validation reports a failure.

---

# 101. readiness.py: why parse success is still not enough

readiness.py contains:

    BLOCKING_STATUSES = {
        ...
        "OCR_REQUIRED",
        "INVALID_PDF",
        "DUPLICATE_FILE",
        "NEEDS_LAYOUT_STRATEGY",
        "FAIL",
        "NEEDS_REVIEW",
    }

Then:

    export_is_safe(...)

checks:

    Were all uploaded files parsed?

and:

    Does validation contain a blocking status?

If unsafe:

    Excel/PDF are NOT generated.

This prevents partial reports from looking complete.

---

# 102. report_data.py

This module holds report-level shared calculations.

Examples:

    total credits
    total debits
    covered period
    overall opening/ending balance
    source statement table

It is shared by both Excel and PDF exporters.

That separation prevents the PDF exporter from depending on private internals of the Excel exporter.

---

# 103. Generating Excel: where does the file live?

build_excel_report() uses:

    buffer = BytesIO()

BytesIO is an in-memory binary buffer.

Think of it as:

    "file-like object living in memory"

pandas/openpyxl write the workbook into that buffer.

Then:

    buffer.getvalue()

returns Excel bytes.

We do NOT need to save:

    consolidated.xlsx

onto the server disk just to let the browser download it.

---

# 104. Generating PDF

export_pdf.py uses ReportLab.

Again:

    buffer = BytesIO()

ReportLab builds PDF bytes in memory.

Then Streamlit receives those bytes.

---

# 105. st.download_button()

app.py passes:

    data=result.excel_report

or:

    data=result.pdf_report

These are bytes.

The user's browser receives a downloadable file.

At our app-code level:

    generated report bytes
        ↓
    download response

No permanent database is required.

---

# 106. Streamlit session state

app.py stores:

    st.session_state[
        "consolidation_result"
    ] = process_statements(inputs)

This means the result is kept in Streamlit's server-side session state so a rerun of the page can still display the processed result.

That result contains:

    DataFrames
    totals
    validation
    generated Excel bytes
    generated PDF bytes

When uploads change:

    clear_previous_result()

does:

    st.session_state.pop(
        "consolidation_result",
        None
    )

That removes the old result from application session state.

---

# 107. What makes this an automation tool?

Automation does not require AI.

The automation is the deterministic chain:

    user uploads
        ↓
    loop over PDFs
        ↓
    inspect
        ↓
    extract geometry
        ↓
    detect layout
        ↓
    parse transactions
        ↓
    normalize
        ↓
    validate
        ↓
    combine
        ↓
    calculate totals
        ↓
    create reports

A human used to perform those steps manually.

Software performs them automatically.

That is automation.

---

# 108. One complete transaction trace

Imagine the PDF visually contains:

    Date       Description     Debit    Credit    Balance
    01/14/26   Coffee          5.00               1095.00

## Stage 1

Browser uploads PDF.

## Stage 2

app.py:

    uploaded.getvalue()

creates bytes.

## Stage 3

pipeline.py:

    inspect_and_extract_pdf(...)

checks validity and embedded text.

## Stage 4

parser.py:

    extract_document_layout(
        pdf_bytes
    )

## Stage 5

layout.py:

    page.get_text("words")

produces word tuples.

Conceptually:

    ("01/14/26", x≈40)
    ("Coffee", x≈150)
    ("5.00", x≈400)
    ("1095.00", x≈540)

## Stage 6

_group_words_into_rows()

sees similar Y positions and creates one LayoutRow.

## Stage 7

LedgerColumnsStrategy.matches()

finds:

    Date
    Debit
    Credit
    Balance

header concepts.

Returns True.

## Stage 8

LedgerColumnsStrategy.parse()

calculates column boundaries.

The word:

    "5.00"

falls inside the debit area.

The word:

    "1095.00"

falls inside the balance area.

## Stage 9

money_from_words()

creates:

    Decimal("5.00")
    Decimal("1095.00")

## Stage 10

Create:

    Transaction(
        date=...,
        description="Coffee",
        debit=Decimal("5.00"),
        credit=None,
        balance=Decimal("1095.00"),
        ...
    )

## Stage 11

Transaction goes into pandas table.

## Stage 12

Validation checks it.

## Stage 13

It appears in:

    All Transactions
    Debits & Withdrawals
    monthly totals
    report output

That is the entire path of one row.

---

# 109. A complete example of capitalization normalization

Suppose one bank writes:

    MONEY OUT

Another:

    Money Out

Another PDF extraction gives:

    Money  Out:

normalize() does:

    .lower()

then regex removes non-alphanumeric characters.

All can become:

    moneyout

Then:

    "moneyout" in DEBIT_HEADERS

can be True.

This is different from an LLM understanding language.

It is explicit deterministic text normalization plus predefined financial synonyms.

---

# 110. What is difflib doing?

difflib.SequenceMatcher compares text similarity.

We use it conservatively for cases such as:

    "Running Balanc"

versus:

    "runningbalance"

because PDF extraction may clip characters.

A high threshold is required.

It is not semantic AI.

It is string similarity.

---

# 111. Why do some helper names start with _?

Examples:

    _group_words_into_rows
    _parse_token_date
    _find_currency

Python convention:

    leading underscore
        =
    "internal helper; not intended as the main public API"

Python does not make the function truly private.

It is a convention for developers.

---

# 112. What does None mean?

None means:

    "No value"

Example:

    credit=None

means this transaction has no credit amount.

Example:

    balance=None

means no usable running balance was available.

It is different from:

    Decimal("0.00")

Zero is a known amount.

None means absent/unknown/not available.

---

# 113. What does if value is not None mean?

It asks:

    "Did we actually get a value?"

Example:

    if closing is None:
        closing = last.balance

Meaning:

    If no labeled closing balance was detected,
    use the last running balance if available.

---

# 114. continue versus break versus return

These are worth memorizing conceptually.

## continue

Inside a loop:

    skip remaining work for current item
    move to next loop item

## break

Inside a loop:

    stop this loop entirely

## return

Inside a function:

    stop the entire function
    send result back to caller

Example strategy selection:

    if not parser.matches(layout):
        continue

means:

    try next strategy

But:

    return _enrich_result(...)

means:

    parsing succeeded
    leave parse_statement completely

---

# 115. next(...)

Sectioned parser uses:

    amount_word = next(
        word
        for word in row.words
        if normalize(word.text) == "amount"
    )

next asks:

    "Give me the first generated item."

So it finds the first word in that row whose normalized text equals:

    amount

---

# 116. min(..., key=...)

Example:

    date_word = min(
        date_words,
        key=lambda word: word.x0
    )

This does not mean smallest date.

It means:

    choose the word with smallest x0

In other words:

    the leftmost date-looking word.

---

# 117. Why there are so many small files

It would be possible to put everything in:

    app.py

But then one file would contain:

    frontend
    PDF I/O
    regex
    geometry
    financial parsing
    validation
    Excel
    PDF report
    security

That becomes difficult to understand and dangerous to modify.

Current separation:

    app.py
        browser UI

    pipeline.py
        orchestration

    pdf_inspect.py
        pre-flight

    layout.py
        geometry

    metadata.py
        statement-level metadata

    parser.py
        strategy selection

    generic_parsers.py
        transaction extraction

    models.py
        data structures

    consolidate.py
        normalized tables/summaries

    validate.py
        correctness checks

    readiness.py
        final export gate

    report_data.py
        report summary data

    export_excel.py
        Excel generation

    export_pdf.py
        PDF generation

That separation is intentional.

---

# 118. The reading order I recommend NOW

Do not read alphabetically.

Do not start with generic_parsers.py.

Use this order.

## 1

Read this file:

    CODE_WALKTHROUGH_PDF_TO_REPORT.md

## 2

Read:

    models.py

Ask:

    What objects exist?

## 3

Read:

    app.py

Only focus on:

    file_uploader
    uploaded.getvalue
    process_statements
    render_result

Ignore CSS on first pass.

## 4

Read:

    pipeline.py

Focus on:

    for source_file, pdf_bytes in files

This is the main workflow.

## 5

Read:

    pdf_inspect.py

Now the code you pasted should make sense.

## 6

Read:

    layout.py

Draw:

    document
      page
        row
          word

on paper if needed.

## 7

Read:

    metadata.py

Focus only on:

    extract_statement_metadata

Then trace backward into helper functions.

## 8

Read:

    parser.py

Focus on:

    PARSERS
    parse_statement

## 9

Only now read:

    generic_parsers.py

Start with:

    normalize
    money_from_words
    header aliases
    LedgerColumnsStrategy

Then read the other strategies.

## 10

Read:

    consolidate.py
    validate.py
    readiness.py

## 11

Read:

    report_data.py
    export_excel.py
    export_pdf.py

## 12

Finally inspect:

    tests/

Tests often make difficult code easier because they show concrete expected behavior.

---

# 119. Do not try to understand every regex at once

When you see:

    r"^(\d{1,2})[./-](\d{1,2})[./-](\d{2,4})$"

you do not initially need to memorize regex grammar.

Translate it to English:

    start of string
    1–2 digits
    separator / . or -
    1–2 digits
    separator
    2–4 digits
    end of string

Then understand:

    group 1
    group 2
    group 3

Only later worry about every character.

---

# 120. How to mentally simplify comprehensions

When you see:

    amount_words = [
        word
        for word in row.words
        if word.center_x >= 500
    ]

Translate to:

    amount_words = []

    for word in row.words:
        if word.center_x >= 500:
            amount_words.append(word)

Whenever a comprehension confuses you, expand it this way.

---

# 121. How to mentally simplify nested loops

When you see:

    for page in layout.pages:
        for row in page.rows:
            for word in row.words:

Imagine:

    open first page
        inspect first row
            inspect first word
            inspect second word
        inspect second row
            ...
    open second page
        ...

That is all nested loops mean.

---

# 122. Why pages, rows, and words are tuples later

Temporary construction needs mutation:

    append word
    sort word

So we use lists while building.

After structure is finalized, dataclasses use tuples.

That communicates:

    "This layout should now be treated as fixed input data."

---

# 123. Where does the original plain text go?

Inside pipeline:

    inspection, text = inspect_and_extract_pdf(...)

Then:

    parse_statement(
        text,
        ...,
        pdf_bytes=pdf_bytes
    )

Current parser.py does:

    del text

So that local plain-text reference is discarded from parse_statement.

When the pipeline loop moves on, ordinary local references can later be reclaimed by Python's memory management when nothing references them.

The lasting processing results are the structured objects and DataFrames we keep in ConsolidationResult/session state.

---

# 124. Does layout.py permanently store every PDF word?

No persistent database is created.

layout is a normal local Python object.

During parse_statement:

    layout = extract_document_layout(
        pdf_bytes
    )

The strategies and metadata functions use it.

After parse_statement returns and no remaining reference to that DocumentLayout exists, Python can eventually reclaim that memory.

We retain the normalized result, not the entire PDF layout tree.

---

# 125. What data DOES survive in ConsolidationResult?

The result contains:

    inspections DataFrame
    statements DataFrame
    transactions DataFrame
    monthly_summary DataFrame
    validation DataFrame
    safe_to_export boolean
    blocking_reasons list
    Excel report bytes
    PDF report bytes
    totals

That object is placed in Streamlit session state.

It is there so the browser can display tabs and download buttons after processing.

---

# 126. Important distinction: raw source versus normalized result

Raw source:

    PDF bytes

Intermediate representations:

    plain text string
    word geometry
    rows
    parser objects

Normalized business result:

    Transaction objects
    StatementSummary objects

Presentation result:

    DataFrames
    Excel bytes
    PDF bytes

This layered transformation is the core design.

---

# 127. Why do we parse geometry instead of only text?

Suppose plain extraction gives:

    Date Description Debit Credit Balance
    01/01 Payroll 100.00 1100.00
    01/02 Coffee 5.00 1095.00

This might be easy.

But another PDF may extract table text in a strange order:

    Date
    Description
    Debit
    Credit
    Balance
    01/01
    01/02
    Payroll
    Coffee
    5.00
    100.00
    1100.00
    1095.00

Plain text alone can lose visual relationships.

Coordinates let us recover:

    which words occupy the same row
    which amounts occupy which column

That is why geometry is central.

---

# 128. What if a PDF is only a scanned image?

Then:

    page.get_text("text")

may return no usable embedded text.

Pre-flight marks:

    OCR_REQUIRED

Current app blocks export.

Future OCR would conceptually produce:

    recognized words
        +
    coordinates

Then we could feed similar structured data into the same normalization/validation architecture.

---

# 129. Is the software "reading every bank statement intelligently"?

Not in the human or LLM sense.

It performs deterministic operations:

    extract words
    normalize text
    find structural header patterns
    use coordinates
    parse dates
    parse amounts
    validate arithmetic

Its strength comes from carefully encoded document-processing rules and validation.

---

# 130. One mental picture for parser.py

Imagine three specialists standing in line.

Specialist 1:

    "I understand tables with separate debit and credit columns."

Specialist 2:

    "I understand Amount + Balance ledgers."

Specialist 3:

    "I understand separate deposit and withdrawal sections."

parser.py hands the DocumentLayout to specialist 1 and asks:

    matches?

If no, specialist 2.

If no, specialist 3.

If one says yes:

    parse it

If nobody recognizes it:

    NEEDS_LAYOUT_STRATEGY

No one is allowed to pretend.

---

# 131. One mental picture for validation

Parser says:

    "I think these are the transactions."

Validator says:

    "Prove it."

For example:

    opening
    + credits
    - debits
    =
    closing?

If not:

    FAIL

That separation is a major safety feature.

---

# 132. One mental picture for the complete automation

Input:

    arbitrary supported bank-statement PDF

Transformation:

    bytes
      ↓
    PDF document
      ↓
    words + X/Y
      ↓
    rows
      ↓
    recognized layout family
      ↓
    normalized transactions
      ↓
    validated financial dataset

Output:

    consolidated Excel
    consolidated PDF

That is what we built.

---

# 133. Tiny Python glossary

    def
        define a function

    class
        define a blueprint for objects

    self
        current object inside an instance method

    return
        finish function and send a value back

    None
        no value / unavailable

    if
        conditional branch

    for
        loop

    continue
        move to next loop iteration

    break
        exit current loop

    try / except
        handle exceptions

    with
        use a context-managed resource

    list
        ordered mutable collection

    tuple
        ordered usually-immutable collection

    dict
        key → value mapping

    set
        unique values

    .append(x)
        add one item

    .extend(items)
        add many items

    len(x)
        item count

    any(...)
        True if at least one value is truthy

    all(...)
        True if every value is truthy

    next(...)
        first next generated value

    enumerate(...)
        loop with index + value

    zip(a, b)
        pair items from collections

    lambda
        tiny anonymous function

    Decimal
        exact decimal-number type useful for money

    pd.DataFrame
        pandas table

    re
        regular-expression library

    fitz
        PyMuPDF import name

---

# 134. What to do while reading the code

When a line confuses you, ask four questions:

1. What TYPE is this variable?

Example:

    pdf_bytes
        bytes

2. What SHAPE is this structure?

Example:

    layout.pages
        tuple of PageLayout

3. What does this function RETURN?

Example:

    inspect_and_extract_pdf
        (
            PdfInspection,
            text string
        )

4. Who CALLS this function?

Example:

    process_statements
        calls inspect_and_extract_pdf

This makes large codebases much easier to follow.

---

# 135. The five files I want you to understand first

If the whole repository feels overwhelming, stop trying to read everything.

Understand only these five first:

    1. models.py
    2. app.py
    3. pipeline.py
    4. pdf_inspect.py
    5. layout.py

Once those make sense, move to:

    parser.py

Then:

    generic_parsers.py

You do NOT need to understand every file at once.

---

# 136. The answer to your original question in one paragraph

Where is all the text extracted?

First, pdf_inspect.py opens the in-memory PDF bytes using PyMuPDF's fitz.open(). It loops over each PyMuPDF Page and calls page.get_text("text"), joining the page strings into one plain-text string so we can determine whether embedded text exists. For actual transaction parsing, parser.py then calls layout.py, which opens the same PDF bytes again and calls page.get_text("words"). That second mode returns individual words with coordinates. layout.py groups nearby-Y words into visual rows. parser.py then tries each generic strategy object's matches() method. The first matching strategy's parse() method loops through the reconstructed rows, uses normalized text and X-coordinate column boundaries to build Transaction objects. Those objects are converted into pandas DataFrames, validated, consolidated, and exported.

That paragraph is the complete answer. The rest of this document explains why each part exists.

---

# 137. Final mental model

Do not think:

    "The program magically reads a bank statement."

Think:

    browser uploads bytes

    PyMuPDF understands PDF syntax

    PyMuPDF gives us words and coordinates

    our code groups words into rows

    our code recognizes table structure

    our code maps table cells into Transaction fields

    our code mathematically checks the result

    our code combines validated results

    our code builds downloadable files

Each step is ordinary code.

The complexity comes from carefully chaining many small, understandable steps.
