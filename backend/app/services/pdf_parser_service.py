import logging
import re
from typing import Tuple, List, Dict, Any
from app.core.exceptions import PasswordProtectedException, PageLimitExceededException

logger = logging.getLogger("app.services.pdf_parser")

# Configurable threshold: lines repeating on more than this fraction of pages
# are considered boilerplate headers/footers and will be stripped.
HEADER_FOOTER_REPEAT_THRESHOLD = 0.60

# Number of lines to inspect at the top and bottom of each page for boilerplate detection
HEADER_FOOTER_MARGIN_LINES = 2

# Lazy imports for OCR dependencies to handle environments without tesseract binaries
try:
    import fitz  # PyMuPDF
    import pytesseract
    from pdf2image import convert_from_bytes
    from PIL import Image
    HAS_OCR_DEPENDENCIES = True
except ImportError as e:
    logger.warning(f"OCR libraries missing or PyMuPDF error: {e}. OCR fallback will be disabled.")
    HAS_OCR_DEPENDENCIES = False

def clean_extracted_text(text: str) -> str:
    """
    Cleans extracted text by stripping excessive whitespace and duplicate newlines.
    """
    if not text:
        return ""
    # Standardize horizontal spacing
    text = re.sub(r"[ \t]+", " ", text)
    # Standardize vertical spacing (max two consecutive newlines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalize_for_boilerplate(line: str) -> str:
    """
    Normalizes a line for boilerplate comparison by:
    - Lowercasing
    - Stripping all digit characters (handles changing page numbers like '1', '2', 'Page 12')
    - Collapsing extra whitespace
    This allows 'Page 1' and 'Page 2' to match as the same boilerplate template.
    """
    no_digits = re.sub(r"\d+", "", line)
    collapsed = re.sub(r"\s+", " ", no_digits).strip().lower()
    return collapsed


# OLD: per-page text was returned as-is after extraction with no detection/removal of
# repeating headers/footers (page numbers, "Confidential", document title repeated on
# every page) — this repeated boilerplate polluted chunks and added noise to
# embeddings/retrieval. Replaced below with a document-level repeating-line detection
# and stripping pass applied to all extraction paths (PyMuPDF, pdfplumber, OCR).
# (old per-page text assembly, kept for reference — stripping pass did not exist)

def strip_repeating_header_footer_lines(
    pages_data: List[Dict[str, Any]],
    threshold: float = HEADER_FOOTER_REPEAT_THRESHOLD,
    margin_lines: int = HEADER_FOOTER_MARGIN_LINES
) -> List[Dict[str, Any]]:
    """
    Detects and strips repeating header/footer boilerplate lines from each page's text.

    Strategy:
    - For each page, collect only the first `margin_lines` and last `margin_lines` lines.
    - Normalize each candidate line (strip digits, lowercase) for comparison.
    - A normalized line that appears in margin positions across > threshold% of pages
      is flagged as boilerplate.
    - Strip only flagged lines from the TOP and BOTTOM margins of each page's text.
      Lines from the middle of page content are never touched, even if they repeat.
    - Logs (INFO) every distinct boilerplate line that was stripped, for debuggability.

    Args:
        pages_data: List of page dicts with at least a 'text' key.
        threshold: Fraction of pages on which a line must appear in margins to be stripped.
        margin_lines: How many lines from the top/bottom to consider as header/footer zone.

    Returns:
        Updated pages_data list with boilerplate margin lines removed.
    """
    total_pages = len(pages_data)
    if total_pages < 2:
        # Cannot detect repeating content in a single-page document
        return pages_data

    # Step 1: Gather normalized top/bottom margin lines per page and count occurrences
    # Structure: { normalized_line_str: count_of_pages_it_appeared_in_margins }
    margin_line_counts: Dict[str, int] = {}

    for page in pages_data:
        text = page.get("text", "")
        lines = [l for l in text.splitlines() if l.strip()]
        if not lines:
            continue

        # Collect top and bottom margin lines (deduplicated within this page)
        candidate_lines_this_page = set()
        top_lines = lines[:margin_lines]
        bottom_lines = lines[-margin_lines:]
        for line in top_lines + bottom_lines:
            norm = _normalize_for_boilerplate(line)
            if norm:  # ignore blank normalized lines
                candidate_lines_this_page.add(norm)

        for norm in candidate_lines_this_page:
            margin_line_counts[norm] = margin_line_counts.get(norm, 0) + 1

    # Step 2: Determine which normalized lines exceed the threshold
    min_count = max(2, int(total_pages * threshold))  # at least 2 pages required
    boilerplate_norms: set = {
        norm for norm, count in margin_line_counts.items()
        if count >= min_count
    }

    if not boilerplate_norms:
        logger.info("Header/footer stripping pass: no repeating boilerplate lines detected.")
        return pages_data

    # Log the distinct boilerplate patterns found
    logger.info(
        f"Header/footer stripping pass: detected {len(boilerplate_norms)} boilerplate pattern(s) "
        f"repeating on >= {threshold*100:.0f}% of {total_pages} pages."
    )

    # Step 3: Strip flagged lines ONLY from the top and bottom margins of each page
    for page in pages_data:
        text = page.get("text", "")
        lines = text.splitlines()
        if not lines:
            continue

        # Strip from the TOP margin
        stripped_top_count = 0
        while lines and stripped_top_count < margin_lines:
            stripped = lines[0].strip()
            if stripped and _normalize_for_boilerplate(stripped) in boilerplate_norms:
                logger.info(
                    f"Header/footer stripping pass: removed top-margin line from page "
                    f"{page.get('page_number', '?')}: {repr(stripped)}"
                )
                lines.pop(0)
                stripped_top_count += 1
            else:
                break  # stop as soon as a non-boilerplate line is encountered

        # Strip from the BOTTOM margin
        stripped_bottom_count = 0
        while lines and stripped_bottom_count < margin_lines:
            stripped = lines[-1].strip()
            if stripped and _normalize_for_boilerplate(stripped) in boilerplate_norms:
                logger.info(
                    f"Header/footer stripping pass: removed bottom-margin line from page "
                    f"{page.get('page_number', '?')}: {repr(stripped)}"
                )
                lines.pop()
                stripped_bottom_count += 1
            else:
                break  # stop as soon as a non-boilerplate line is encountered

        updated_text = clean_extracted_text("\n".join(lines))
        page["text"] = updated_text
        page["char_count"] = len(updated_text)

    return pages_data

# OLD: parsed PDF page text using only PyMuPDF (fitz), without column detection or table extraction — replaced below to add pdfplumber-based column/table detection and extraction
# def parse_pdf_pages(file_bytes: bytes) -> Tuple[List[Dict[str, Any]], bool]:
#     """
#     Parses a PDF file from bytes page-by-page.
#     Supports password checks, page count validation, and OCR fallback.
#     """
#     try:
#         import fitz
#     except ImportError:
#         raise RuntimeError("PyMuPDF (fitz) is not installed in the virtual environment.")
# 
#     doc = fitz.open(stream=file_bytes, filetype="pdf")
#     try:
#         # 1. Check if the document is password-protected
#         if doc.is_encrypted:
#             # Try authenticating with empty password
#             if not doc.authenticate(""):
#                 raise PasswordProtectedException("Password protected PDF files are not supported.")
# 
#         # 2. Check page limit constraint (100 pages maximum)
#         page_count = len(doc)
#         if page_count > 100:
#             raise PageLimitExceededException(f"PDF page count ({page_count}) exceeds allowable limit of 100 pages.")
# 
#         pages_data = []
#         ocr_triggered = False
# 
#         for page_idx in range(page_count):
#             page = doc[page_idx]
#             extracted_text = page.get_text()
#             cleaned_text = clean_extracted_text(extracted_text)
# 
#             # Determine if OCR fallback should trigger:
#             # - Extracted text character length is < 100
#             # - Page has drawings, images or measurable dimensions (not completely empty)
#             has_content_visuals = len(page.get_images()) > 0 or len(page.get_drawings()) > 0
#             if len(cleaned_text) < 100 and has_content_visuals:
#                 if HAS_OCR_DEPENDENCIES:
#                     try:
#                         logger.info(f"Triggering OCR fallback for page {page_idx + 1} (chars: {len(cleaned_text)})")
#                         # Convert only this specific page to image
#                         images = convert_from_bytes(file_bytes, first_page=page_idx + 1, last_page=page_idx + 1)
#                         if images:
#                             ocr_text = pytesseract.image_to_string(images[0])
#                             cleaned_ocr = clean_extracted_text(ocr_text)
#                             if len(cleaned_ocr) > len(cleaned_text):
#                                 cleaned_text = cleaned_ocr
#                                 ocr_triggered = True
#                                 logger.info(f"OCR successfully extracted text for page {page_idx + 1}.")
#                     except Exception as ocr_err:
#                         # Log error and fallback to standard text (graceful degradation)
#                         logger.warning(f"OCR execution failed on page {page_idx + 1}: {ocr_err}. Falling back to default.")
#                 else:
#                     logger.warning(f"OCR libraries not fully loaded. Skipping OCR check for page {page_idx + 1}.")
# 
#             pages_data.append({
#                 "page_number": page_idx + 1,
#                 "text": cleaned_text,
#                 "char_count": len(cleaned_text)
#             })
# 
#         return pages_data, ocr_triggered
#     finally:
#         doc.close()

import io
import pdfplumber

# Silencing pdfminer and pdfplumber loggers to prevent debug logging loops
logging.getLogger("pdfminer").setLevel(logging.WARNING)
logging.getLogger("pdfplumber").setLevel(logging.WARNING)
logging.getLogger("pdfminer").propagate = False
logging.getLogger("pdfplumber").propagate = False

def extract_document_metadata(first_page) -> Tuple[Optional[str], Optional[str]]:
    """
    Analyzes page 1 of a PDF to extract likely Title and Author List.
    Uses font size and positioning heuristics from PyMuPDF get_text("dict").
    """
    try:
        page_dict = first_page.get_text("dict")
        blocks = page_dict.get("blocks", [])
    except Exception as e:
        logger.warning(f"Failed to get_text('dict') from first page: {e}")
        return None, None

    text_blocks = []
    for b in blocks:
        if b.get("type") == 0:  # text block
            block_text = ""
            max_size = 0.0
            for line in b.get("lines", []):
                for span in line.get("spans", []):
                    span_text = span.get("text", "")
                    if span_text.strip():
                        block_text += span_text + " "
                        max_size = max(max_size, span.get("size", 0.0))
            block_text = block_text.strip()
            if block_text:
                text_blocks.append({
                    "text": block_text,
                    "bbox": b.get("bbox"),
                    "max_font_size": max_size
                })

    if not text_blocks:
        return None, None

    # Find the overall maximum font size on the page
    overall_max_font = max(b["max_font_size"] for b in text_blocks)
    if overall_max_font <= 0:
        return None, None

    # Title is typically the block(s) with the maximum font size (or within 10% of it)
    title_blocks = [
        b for b in text_blocks 
        if b["max_font_size"] >= overall_max_font * 0.9
    ]
    
    if not title_blocks:
        return None, None

    # Sort title blocks by y0 (top to bottom)
    title_blocks.sort(key=lambda x: x["bbox"][1])
    title = " ".join(b["text"] for b in title_blocks).strip()

    title_y0 = min(b["bbox"][1] for b in title_blocks)
    title_y1 = max(b["bbox"][3] for b in title_blocks)

    # Candidates for authors are blocks below the title
    below_title_blocks = [
        b for b in text_blocks
        if b["bbox"][1] >= title_y1 - 5 and b not in title_blocks
    ]
    # Sort by vertical position
    below_title_blocks.sort(key=lambda x: x["bbox"][1])

    author_texts = []
    for b in below_title_blocks:
        txt = b["text"]
        # Stop if we hit Abstract or Introduction header
        if re.search(r"\b(?:abstract|introduction)\b", txt, re.IGNORECASE):
            break
        # Also stop if we hit some other indicators of body text if we already have some authors
        if len(txt) > 300 and author_texts:
            break
        author_texts.append(txt)

    # Join the author list. If nothing was collected, return None.
    authors = "\n".join(author_texts).strip() if author_texts else None

    # Limit lengths to reasonable DB limits
    cleaned_title = clean_extracted_text(title)
    if cleaned_title:
        cleaned_title = cleaned_title[:500]
    cleaned_authors = clean_extracted_text(authors) if authors else None
    if cleaned_authors:
        cleaned_authors = cleaned_authors[:1000]

    return cleaned_title or None, cleaned_authors or None

def parse_pdf_pages(file_bytes: bytes) -> Tuple[List[Dict[str, Any]], bool]:
    """
    Parses a PDF file from bytes page-by-page.
    Supports password checks, page count validation, and OCR fallback.
    Uses pdfplumber for multi-column layout detection/splitting and table extraction.
    """
    try:
        import fitz
    except ImportError:
        raise RuntimeError("PyMuPDF (fitz) is not installed in the virtual environment.")

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pdf_plumber_client = None
    try:
        # 1. Check if the document is password-protected
        if doc.is_encrypted:
            # Try authenticating with empty password
            if not doc.authenticate(""):
                raise PasswordProtectedException("Password protected PDF files are not supported.")

        # 2. Check page limit constraint (100 pages maximum)
        page_count = len(doc)
        if page_count > 100:
            raise PageLimitExceededException(f"PDF page count ({page_count}) exceeds allowable limit of 100 pages.")

        pages_data = []
        ocr_triggered = False

        # Extract title and authors from page 1 using fitz
        extracted_title = None
        extracted_authors = None
        if page_count > 0:
            try:
                extracted_title, extracted_authors = extract_document_metadata(doc[0])
                logger.info(f"Page 1 metadata extraction: Title='{extracted_title}', Authors='{extracted_authors}'")
            except Exception as metadata_err:
                logger.warning(f"Could not extract metadata from first page: {metadata_err}")


        # Open pdfplumber for column/table processing
        try:
            pdf_plumber_client = pdfplumber.open(io.BytesIO(file_bytes))
        except Exception as plumber_err:
            logger.warning(f"Could not initialize pdfplumber client: {plumber_err}. Column/table extraction will be disabled.")
            pdf_plumber_client = None

        for page_idx in range(page_count):
            page = doc[page_idx]
            page_width = page.rect.width
            mid_x = page_width / 2

            # Try column detection on PyMuPDF layout blocks
            blocks = page.get_text("blocks")
            is_multi_column = False
            text_blocks = [b for b in blocks if b[6] == 0 and b[4].strip()]
            if len(text_blocks) >= 4:
                left_cnt = 0
                right_cnt = 0
                spanning_cnt = 0
                for x0, y0, x1, y1, txt, b_no, b_type in text_blocks:
                    if x1 <= mid_x + 15:
                        left_cnt += 1
                    elif x0 >= mid_x - 15:
                        right_cnt += 1
                    else:
                        spanning_cnt += 1
                if left_cnt >= 2 and right_cnt >= 2 and spanning_cnt <= (0.25 * len(text_blocks)):
                    is_multi_column = True

            # Perform text extraction
            extracted_text = ""
            was_multi_column = False
            had_tables = False

            plumber_page = None
            if pdf_plumber_client and page_idx < len(pdf_plumber_client.pages):
                plumber_page = pdf_plumber_client.pages[page_idx]

            # If multi-column detected, use pdfplumber split extraction
            if is_multi_column and plumber_page:
                try:
                    logger.info(f"Multi-column layout detected on page {page_idx + 1}. Using pdfplumber column split extraction.")
                    w = plumber_page.width
                    h = plumber_page.height
                    pmid_x = w / 2
                    
                    left_crop = plumber_page.within_bbox((0, 0, pmid_x, h))
                    left_text = left_crop.extract_text() or ""
                    
                    right_crop = plumber_page.within_bbox((pmid_x, 0, w, h))
                    right_text = right_crop.extract_text() or ""
                    
                    extracted_text = left_text + "\n\n" + right_text
                    was_multi_column = True
                except Exception as col_err:
                    logger.warning(f"pdfplumber column extraction failed on page {page_idx + 1}: {col_err}. Falling back to PyMuPDF.")
                    extracted_text = page.get_text()
            else:
                extracted_text = page.get_text()

            # Clean the extracted text
            cleaned_text = clean_extracted_text(extracted_text)

            # Table extraction using pdfplumber
            table_texts = []
            if plumber_page:
                try:
                    tables = plumber_page.extract_tables()
                    if tables:
                        had_tables = True
                        for tbl_idx, table in enumerate(tables):
                            if not table or not table[0]:
                                continue
                            headers = [str(h or f"Column {i+1}").strip() for i, h in enumerate(table[0])]
                            table_lines = [f"Table {tbl_idx + 1}:"]
                            for r_idx, row in enumerate(table[1:]):
                                row_items = []
                                for c_idx, val in enumerate(row):
                                    col_name = headers[c_idx] if c_idx < len(headers) else f"Column {c_idx+1}"
                                    val_str = str(val or "").strip()
                                    row_items.append(f"{col_name} is {val_str}")
                                table_lines.append(f"Row {r_idx + 1}: " + ", ".join(row_items))
                            table_texts.append("\n".join(table_lines))
                except Exception as tbl_err:
                    logger.warning(f"pdfplumber table extraction failed on page {page_idx + 1}: {tbl_err}")

            # OLD: extracted tables were flattened entirely into natural-language 
            # sentences and merged into the surrounding page text before chunking — 
            # acceptable for general Q&A, but risks losing precise row/column 
            # relationships for specific numeric lookups (e.g. "what was Q3 revenue 
            # specifically"), and a table could get arbitrarily split across two 
            # chunks by the character-based splitter. Replaced below to treat each 
            # extracted table as its own atomic, unsplittable chunk.
            # (old table-flattening code, kept for reference)
            # if table_natural_text:
            #     if cleaned_text:
            #         cleaned_text = cleaned_text + "\n\n" + table_natural_text
            #     else:
            #         cleaned_text = table_natural_text

            # Determine if OCR fallback should trigger:
            # - Extracted text character length is < 100
            # - Page has drawings, images or measurable dimensions (not completely empty)
            has_content_visuals = len(page.get_images()) > 0 or len(page.get_drawings()) > 0
            # OLD: OCR always ran with default language (eng) only — replaced below to support multilingual OCR based on eng+hin+spa+fra+deu and log warning if output is still short
            # if len(cleaned_text) < 100 and has_content_visuals:
            #     if HAS_OCR_DEPENDENCIES:
            #         try:
            #             logger.info(f"Triggering OCR fallback for page {page_idx + 1} (chars: {len(cleaned_text)})")
            #             # Convert only this specific page to image
            #             images = convert_from_bytes(file_bytes, first_page=page_idx + 1, last_page=page_idx + 1)
            #             if images:
            #                 ocr_text = pytesseract.image_to_string(images[0])
            #                 cleaned_ocr = clean_extracted_text(ocr_text)
            #                 if len(cleaned_ocr) > len(cleaned_text):
            #                     cleaned_text = cleaned_ocr
            #                     ocr_triggered = True
            #                     logger.info(f"OCR successfully extracted text for page {page_idx + 1}.")
            #         except Exception as ocr_err:
            #             # Log error and fallback to standard text (graceful degradation)
            #             logger.warning(f"OCR execution failed on page {page_idx + 1}: {ocr_err}. Falling back to default.")
            #     else:
            #         logger.warning(f"OCR libraries not fully loaded. Skipping OCR check for page {page_idx + 1}.")

            if len(cleaned_text) < 100 and has_content_visuals:
                if HAS_OCR_DEPENDENCIES:
                    try:
                        logger.info(f"Triggering OCR fallback for page {page_idx + 1} (chars: {len(cleaned_text)})")
                        # Convert only this specific page to image
                        images = convert_from_bytes(file_bytes, first_page=page_idx + 1, last_page=page_idx + 1)
                        if images:
                            ocr_text = pytesseract.image_to_string(images[0], lang="eng+hin+spa+fra+deu")
                            cleaned_ocr = clean_extracted_text(ocr_text)
                            
                            # Log warning if the OCR text is still suspiciously short after the multi-language attempt
                            if len(cleaned_ocr) < 100:
                                logger.warning(
                                    f"OCR output on page {page_idx + 1} is suspiciously short ({len(cleaned_ocr)} chars). "
                                    f"OCR may have failed to recognize the document's language properly."
                                )
                            
                            if len(cleaned_ocr) > len(cleaned_text):
                                cleaned_text = cleaned_ocr
                                ocr_triggered = True
                                logger.info(f"OCR successfully extracted text for page {page_idx + 1}.")
                    except Exception as ocr_err:
                        # Log error and fallback to standard text (graceful degradation)
                        logger.warning(f"OCR execution failed on page {page_idx + 1}: {ocr_err}. Falling back to default.")
                else:
                    logger.warning(f"OCR libraries not fully loaded. Skipping OCR check for page {page_idx + 1}.")

            # OLD: pages_data append block without extracted_title and extracted_authors metadata, kept for reference
            # pages_data.append({
            #     "page_number": page_idx + 1,
            #     "text": cleaned_text,
            #     "char_count": len(cleaned_text),
            #     "was_multi_column": was_multi_column,
            #     "had_tables": had_tables,
            #     "tables": table_texts
            # })
            
            page_dict = {
                "page_number": page_idx + 1,
                "text": cleaned_text,
                "char_count": len(cleaned_text),
                "was_multi_column": was_multi_column,
                "had_tables": had_tables,
                "tables": table_texts
            }
            if page_idx == 0:
                page_dict["extracted_title"] = extracted_title
                page_dict["extracted_authors"] = extracted_authors
            pages_data.append(page_dict)


        # Document-level repeating header/footer stripping pass.
        # Runs AFTER all per-page extraction (PyMuPDF, pdfplumber, OCR) is complete
        # and BEFORE pages_data is returned for chunking.
        # Safe to apply to all extraction paths — it only strips top/bottom margin lines.
        pages_data = strip_repeating_header_footer_lines(pages_data)

        return pages_data, ocr_triggered
    finally:
        doc.close()
        if pdf_plumber_client:
            try:
                pdf_plumber_client.close()
            except Exception:
                pass

