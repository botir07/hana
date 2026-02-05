"""
Full-disk (or selected roots) text indexer for local RAG.

Usage example:
    python tools/full_index.py --roots "C:\\" --persist "C:\\Users\\world\\Desktop\\hana_index"

What it does:
  * Recursively walks given roots.
  * Reads text-like files (UTF-8 best-effort, PDF via pypdf).
  * Chunks content and stores in a Chroma DB collection with sentence-transformer embeddings.

Notes:
  * Binary files are skipped by size/extension heuristics.
  * Locked files are skipped with a warning; indexing continues.
  * Embedding model (~90 MB) downloads on first run.
"""

from __future__ import annotations

import argparse
import hashlib
import mimetypes
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

try:  # Delay hard failure until main() so we can emit a helpful message.
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    _IMPORT_ERROR = None
except ModuleNotFoundError as exc:
    chromadb = None  # type: ignore
    SentenceTransformerEmbeddingFunction = None  # type: ignore
    _IMPORT_ERROR = exc


DEFAULT_EXT_ALLOW = {
    ".txt",
    ".md",
    ".py",
    ".js",
    ".ts",
    ".json",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".toml",
    ".html",
    ".htm",
    ".css",
    ".csv",
    ".log",
    ".xml",
    ".pdf",
}


def configure_streams() -> None:
    """Make stdout/stderr UTF-8 friendly and non-fatal on bad chars."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
        except Exception:
            # Some environments (e.g., redirected output) may not support reconfigure.
            pass


def iter_files(roots: List[Path]) -> Iterable[Path]:
    for root in roots:
        if not root.exists():
            print(f"[skip] missing root {root}")
            continue
        for path in root.rglob("*"):
            if path.is_file():
                yield path


def is_text_like(path: Path, size_limit_mb: int) -> bool:
    if path.suffix.lower() not in DEFAULT_EXT_ALLOW:
        return False
    if path.stat().st_size > size_limit_mb * 1024 * 1024:
        return False
    # Quick mime check for obvious binaries
    mime, _ = mimetypes.guess_type(str(path))
    if mime is not None and any(mime.startswith(prefix) for prefix in ("audio", "video", "image", "application/vnd")):
        return False
    return True


def read_text(path: Path) -> Optional[str]:
    if path.suffix.lower() == ".pdf":
        try:
            import pypdf

            reader = pypdf.PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            print(f"[warn] pdf read failed {path}: {exc}")
            return None
    try:
        data = path.read_bytes()
        return data.decode("utf-8", errors="ignore")
    except Exception as exc:
        print(f"[warn] read failed {path}: {exc}")
        return None


def chunk_text(text: str, max_len: int, overlap: int) -> Iterable[str]:
    if max_len <= overlap:
        raise ValueError("max_len must be greater than overlap")
    step = max_len - overlap
    for start in range(0, len(text), step):
        yield text[start : start + max_len]


def make_id(path: Path, chunk_idx: int) -> str:
    h = hashlib.sha1(f"{path}::{chunk_idx}".encode("utf-8")).hexdigest()
    return f"{h}-{chunk_idx}"


def chunk_upserts(col, ids: list[str], docs: list[str], metas: list[dict], batch: int) -> None:
    """Upsert in safe batches to avoid chromadb batch limit errors."""
    for i in range(0, len(docs), batch):
        col.upsert(
            ids=ids[i : i + batch],
            documents=docs[i : i + batch],
            metadatas=metas[i : i + batch],
        )


def process_path(path: Path, size_limit_mb: int, max_len: int, overlap: int):
    if not is_text_like(path, size_limit_mb):
        return None
    text = read_text(path)
    if not text:
        return None
    docs = list(chunk_text(text, max_len=max_len, overlap=overlap))
    if not docs:
        return None
    ids = [make_id(path, i) for i in range(len(docs))]
    metadatas = [{"path": str(path), "chunk": i} for i in range(len(docs))]
    return ids, docs, metadatas, path


def index_paths(
    roots: List[Path],
    persist: Path,
    collection: str,
    size_limit_mb: int,
    max_len: int,
    overlap: int,
    batch_size: int,
    max_workers: int,
) -> None:
    client = chromadb.PersistentClient(path=str(persist))
    embed = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    col = client.get_or_create_collection(name=collection, embedding_function=embed)

    total_files = 0
    total_chunks = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for result in pool.map(lambda p: process_path(p, size_limit_mb, max_len, overlap), iter_files(roots)):
            if not result:
                continue
            ids, docs, metadatas, path = result
            chunk_upserts(col, ids=ids, docs=docs, metas=metadatas, batch=batch_size)
            total_files += 1
            total_chunks += len(docs)
            if total_files % 50 == 0:
                print(f"[progress] files={total_files} chunks={total_chunks} last={path}")

    print(f"[done] indexed files={total_files} chunks={total_chunks} -> {persist} (collection={collection})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Full/directory text indexer for local RAG.")
    parser.add_argument(
        "--roots",
        nargs="+",
        required=True,
        help="Root folders to crawl, e.g. C:\\ or C:\\Users\\world",
    )
    parser.add_argument(
        "--persist",
        required=True,
        help="Folder to store Chroma DB (will be created if missing)",
    )
    parser.add_argument("--collection", default="full_disk", help="Chroma collection name")
    parser.add_argument("--size-limit-mb", type=int, default=8, help="Skip files larger than this (MB)")
    parser.add_argument("--max-len", type=int, default=6000, help="Chunk length in characters")
    parser.add_argument("--overlap", type=int, default=200, help="Chunk overlap in characters")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=8000,
        help="Max docs per upsert batch (must be <= chromadb server limit; default 8000)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=max(os.cpu_count() or 4, 4),
        help="Number of parallel threads for reading/chunking (use more to push CPU).",
    )
    return parser.parse_args()


def main() -> None:
    configure_streams()
    if sys.version_info >= (3, 13):
        print(
            "[error] Full scan requires Python 3.10–3.12 because chromadb/numpy wheels "
            "are not yet available for this Python version. Please run HANA in a 3.10–3.12 "
            "virtual environment and install requirements.txt, then try again."
        )
        sys.exit(1)
    if _IMPORT_ERROR:
        print(
            "[error] chromadb (and dependencies) not installed. "
            "Run: pip install -r requirements.txt   (inside a Python 3.10–3.12 venv)\n"
            f"Details: {_IMPORT_ERROR}"
        )
        sys.exit(1)
    args = parse_args()
    roots = [Path(r).resolve() for r in args.roots]
    persist = Path(args.persist).resolve()
    persist.mkdir(parents=True, exist_ok=True)
    index_paths(
        roots=roots,
        persist=persist,
        collection=args.collection,
        size_limit_mb=args.size_limit_mb,
        max_len=args.max_len,
        overlap=args.overlap,
        batch_size=args.batch_size,
        max_workers=args.max_workers,
    )


if __name__ == "__main__":
    main()
