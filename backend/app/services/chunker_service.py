import logging
from typing import List, Dict, Any
from app.core.config import settings

logger = logging.getLogger("app.services.chunker")

try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    RecursiveCharacterTextSplitter = None

# OLD: chunked document pages extracting only basic page number and indexes — replaced below to forward was_multi_column and had_tables flags to the chunks metadata
# def chunk_document_pages(
#     pages: List[Dict[str, Any]],
#     chunk_size: int | None = None,
#     chunk_overlap: int | None = None
# ) -> List[Dict[str, Any]]:
#     """
#     Splits extracted PDF page structures into smaller text chunks using RecursiveCharacterTextSplitter.
#     Attaches chunk_index and page_number metadata to each chunk.
#     """
#     global RecursiveCharacterTextSplitter
#     if RecursiveCharacterTextSplitter is None:
#         try:
#             from langchain_text_splitters import RecursiveCharacterTextSplitter
#         except ImportError:
#             raise RuntimeError("langchain-text-splitters is not installed in the virtual environment.")
# 
#     size = chunk_size if chunk_size is not None else settings.DEFAULT_CHUNK_SIZE
#     overlap = chunk_overlap if chunk_overlap is not None else settings.DEFAULT_CHUNK_OVERLAP
# 
#     # Instantiate text splitter using LangChain
#     splitter = RecursiveCharacterTextSplitter(
#         chunk_size=size,
#         chunk_overlap=overlap,
#         length_function=len
#     )
# 
#     chunks = []
#     chunk_index = 0
# 
#     for page in pages:
#         page_number = page.get("page_number")
#         text = page.get("text", "")
# 
#         # Skip empty pages
#         if not text.strip():
#             continue
# 
#         # Split text of this single page to keep page number metadata bounds
#         split_texts = splitter.split_text(text)
#         for snippet in split_texts:
#             trimmed_snippet = snippet.strip()
#             if not trimmed_snippet:
#                 continue
# 
#             chunks.append({
#                 "chunk_index": chunk_index,
#                 "page_number": page_number,
#                 "text": trimmed_snippet,
#                 "char_count": len(trimmed_snippet)
#             })
#             chunk_index += 1
# 
#     logger.info(
#         f"Document chunking complete: partitioned {len(pages)} pages into {len(chunks)} chunks "
#         f"(chunk_size={size}, overlap={overlap})"
#     )
#     return chunks

# OLD: only produced flat child-sized chunks (450 chars/90 overlap) with no 
# relationship to a larger surrounding context — replaced/extended below to 
# also group chunks into parent-level groupings for parent-document 
# retrieval.
# def chunk_document_pages(
#     pages: List[Dict[str, Any]],
#     chunk_size: int | None = None,
#     chunk_overlap: int | None = None
# ) -> List[Dict[str, Any]]:
#     global RecursiveCharacterTextSplitter
#     if RecursiveCharacterTextSplitter is None:
#         try:
#             from langchain_text_splitters import RecursiveCharacterTextSplitter
#         except ImportError:
#             raise RuntimeError("langchain-text-splitters is not installed in the virtual environment.")
# 
#     size = chunk_size if chunk_size is not None else settings.DEFAULT_CHUNK_SIZE
#     overlap = chunk_overlap if chunk_overlap is not None else settings.DEFAULT_CHUNK_OVERLAP
# 
#     splitter = RecursiveCharacterTextSplitter(
#         chunk_size=size,
#         chunk_overlap=overlap,
#         length_function=len,
#         separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""]
#     )
# 
#     chunks = []
#     chunk_index = 0
# 
#     for page in pages:
#         page_number = page.get("page_number")
#         text = page.get("text", "")
#         was_multi_column = page.get("was_multi_column", False)
#         had_tables = page.get("had_tables", False)
# 
#         if not text.strip():
#             continue
# 
#         split_texts = splitter.split_text(text)
#         for snippet in split_texts:
#             trimmed_snippet = snippet.strip()
#             if not trimmed_snippet:
#                 continue
# 
#             chunks.append({
#                 "chunk_index": chunk_index,
#                 "page_number": page_number,
#                 "text": trimmed_snippet,
#                 "char_count": len(trimmed_snippet),
#                 "was_multi_column": was_multi_column,
#                 "had_tables": had_tables
#             })
#             chunk_index += 1
# 
#     logger.info(
#         f"Document chunking complete: partitioned {len(pages)} pages into {len(chunks)} chunks "
#         f"(chunk_size={size}, overlap={overlap})"
#     )
#     return chunks

def chunk_document_pages(
    pages: List[Dict[str, Any]],
    chunk_size: int | None = None,
    chunk_overlap: int | None = None
) -> List[Dict[str, Any]]:
    """
    Splits extracted PDF page structures into smaller text chunks using RecursiveCharacterTextSplitter.
    Attaches chunk_index, page_number, was_multi_column, and had_tables metadata.
    Also groups child chunks into larger parent chunks (~1500-2000 characters) and links them.
    """
    global RecursiveCharacterTextSplitter
    if RecursiveCharacterTextSplitter is None:
        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter
        except ImportError:
            raise RuntimeError("langchain-text-splitters is not installed in the virtual environment.")

    size = chunk_size if chunk_size is not None else settings.DEFAULT_CHUNK_SIZE
    overlap = chunk_overlap if chunk_overlap is not None else settings.DEFAULT_CHUNK_OVERLAP

    # Instantiate text splitter using LangChain
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=size,
        chunk_overlap=overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", "! ", "? ", " ", ""]
    )

    child_chunks = []
    chunk_index = 0

    # OLD: chunking page loop without title page atomic chunk extraction, kept for reference
    # for page in pages:
    #     page_number = page.get("page_number")
    #     text = page.get("text", "")
    #     was_multi_column = page.get("was_multi_column", False)
    #     had_tables = page.get("had_tables", False)
    # 
    #     # Split text of this single page to keep page number metadata bounds
    #     if text.strip():
    #         split_texts = splitter.split_text(text)
    #         for snippet in split_texts:
    #             trimmed_snippet = snippet.strip()
    #             if not trimmed_snippet:
    #                 continue
    # 
    #             child_chunks.append({
    #                 "chunk_index": chunk_index,
    #                 "page_number": page_number,
    #                 "text": trimmed_snippet,
    #                 "char_count": len(trimmed_snippet),
    #                 "was_multi_column": was_multi_column,
    #                 "had_tables": had_tables,
    #                 "is_table_chunk": False
    #             })
    #             chunk_index += 1
    # 
    #     # Process standalone tables if present on this page
    #     for table_text in page.get("tables", []):
    #         trimmed_table = table_text.strip()
    #         if not trimmed_table:
    #             continue
    # 
    #         child_chunks.append({
    #             "chunk_index": chunk_index,
    #             "page_number": page_number,
    #             "text": trimmed_table,
    #             "char_count": len(trimmed_table),
    #             "was_multi_column": was_multi_column,
    #             "had_tables": True,
    #             "is_table_chunk": True
    #         })
    #         chunk_index += 1

    for page in pages:
        page_number = page.get("page_number")
        text = page.get("text", "")
        was_multi_column = page.get("was_multi_column", False)
        had_tables = page.get("had_tables", False)

        # Process title page metadata if present on page 1
        if page_number == 1:
            extracted_title = page.get("extracted_title")
            extracted_authors = page.get("extracted_authors")
            if extracted_title or extracted_authors:
                title_text = extracted_title or "Unknown Title"
                authors_text = extracted_authors or "Unknown Authors"
                chunk_text = f"Document Title: {title_text}\nAuthors: {authors_text}"
                child_chunks.append({
                    "chunk_index": chunk_index,
                    "page_number": page_number,
                    "text": chunk_text,
                    "char_count": len(chunk_text),
                    "was_multi_column": was_multi_column,
                    "had_tables": had_tables,
                    "is_table_chunk": False,
                    "is_title_page_chunk": True
                })
                chunk_index += 1

        # Split text of this single page to keep page number metadata bounds
        if text.strip():
            split_texts = splitter.split_text(text)
            for snippet in split_texts:
                trimmed_snippet = snippet.strip()
                if not trimmed_snippet:
                    continue

                child_chunks.append({
                    "chunk_index": chunk_index,
                    "page_number": page_number,
                    "text": trimmed_snippet,
                    "char_count": len(trimmed_snippet),
                    "was_multi_column": was_multi_column,
                    "had_tables": had_tables,
                    "is_table_chunk": False,
                    "is_title_page_chunk": False
                })
                chunk_index += 1

        # Process standalone tables if present on this page
        for table_text in page.get("tables", []):
            trimmed_table = table_text.strip()
            if not trimmed_table:
                continue

            child_chunks.append({
                "chunk_index": chunk_index,
                "page_number": page_number,
                "text": trimmed_table,
                "char_count": len(trimmed_table),
                "was_multi_column": was_multi_column,
                "had_tables": True,
                "is_table_chunk": True,
                "is_title_page_chunk": False
            })
            chunk_index += 1

    # Second coarser pass: group small child chunks into parent chunks of ~1500-2000 characters
    import uuid
    parent_groups = []
    current_group = []
    current_len = 0

    # OLD: parent group assignment that only isolated table chunks, kept for reference
    # for cc in child_chunks:
    #     if cc.get("is_table_chunk"):
    #         if current_group:
    #             parent_groups.append(current_group)
    #             current_group = []
    #             current_len = 0
    #         parent_groups.append([cc])
    #         continue

    for cc in child_chunks:
        # If it is a table chunk or title page chunk, isolate it as a standalone parent group so it remains atomic
        if cc.get("is_table_chunk") or cc.get("is_title_page_chunk"):
            if current_group:
                parent_groups.append(current_group)
                current_group = []
                current_len = 0
            parent_groups.append([cc])
            continue


        cc_len = len(cc["text"])
        # If adding this child chunk exceeds 2000 chars OR current group already has >= 1500 chars,
        # start a new parent group.
        if current_group and (current_len >= 1500 or current_len + cc_len + 1 > 2000):
            parent_groups.append(current_group)
            current_group = []
            current_len = 0
        current_group.append(cc)
        current_len += cc_len + (1 if current_len > 0 else 0)

    if current_group:
        parent_groups.append(current_group)

    # Process each parent group and inject parent_chunk_id, parent_chunk_text, and parent_page_range metadata
    for group in parent_groups:
        parent_id = str(uuid.uuid4())
        parent_text = "\n\n".join([c["text"] for c in group])

        # Get parent page range
        pages_in_group = [c["page_number"] for c in group if c.get("page_number") is not None]
        if pages_in_group:
            min_p = min(pages_in_group)
            max_p = max(pages_in_group)
            if min_p == max_p:
                page_range = str(min_p)
            else:
                page_range = f"{min_p}-{max_p}"
        else:
            page_range = "unknown"

        for cc in group:
            cc["parent_chunk_id"] = parent_id
            cc["parent_chunk_text"] = parent_text
            cc["parent_page_range"] = page_range

    logger.info(
        f"Document chunking complete: partitioned {len(pages)} pages into {len(child_chunks)} chunks "
        f"and grouped them into {len(parent_groups)} parent chunks (chunk_size={size}, overlap={overlap})"
    )
    return child_chunks

