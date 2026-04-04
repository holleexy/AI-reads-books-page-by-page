from pathlib import Path
from dataclasses import dataclass
from pydantic import BaseModel
import json
import anthropic
import os
import time
import hashlib
import fitz  # PyMuPDF
from termcolor import colored
from datetime import datetime
import shutil

ZAI_BASE_URL = "https://api.z.ai/api/anthropic"
SAVE_INTERVAL = 10

SYSTEM_PROMPT_EXTRACT = """Analyze this page as if you're studying from a book.

SKIP content if the page contains:
- Table of contents
- Chapter listings
- Index pages
- Blank pages
- Copyright information
- Publishing details
- References or bibliography
- Acknowledgments

DO extract knowledge if the page contains:
- Preface content that explains important concepts
- Actual educational content
- Key definitions and concepts
- Important arguments or theories
- Examples and case studies
- Significant findings or conclusions
- Methodologies or frameworks
- Critical analyses or interpretations

For valid content:
- Set has_content to true
- Extract detailed, learnable knowledge points
- Include important quotes or key statements
- Capture examples with their context
- Preserve technical terms and definitions

For pages to skip:
- Set has_content to false
- Return empty knowledge list"""

SYSTEM_PROMPT_ANALYSIS = """Create a comprehensive summary of the provided content in a concise but detailed way, using markdown format.

Use markdown formatting:
- ## for main sections
- ### for subsections
- Bullet points for lists
- `code blocks` for any code or formulas
- **bold** for emphasis
- *italic* for terminology
- > blockquotes for important notes

Return only the markdown summary, nothing else. Do not say 'here is the summary' or anything like that before or after"""


@dataclass
class BookConfig:
    pdf_path: Path
    base_dir: Path = Path("book_analysis")
    model: str = "glm-5.1"
    analysis_model: str = "glm-5.1"
    analysis_interval: int | None = 20
    test_pages: int | None = 60
    start_page: int = 0
    book_key_override: str | None = None

    @property
    def book_key(self) -> str:
        return self.book_key_override or self.pdf_path.stem

    @property
    def pdf_dir(self) -> Path:
        return self.base_dir / "pdfs"

    @property
    def knowledge_dir(self) -> Path:
        return self.base_dir / "knowledge_bases"

    @property
    def summaries_dir(self) -> Path:
        return self.base_dir / "summaries"

    @property
    def knowledge_file(self) -> Path:
        return self.knowledge_dir / f"{self.book_key}_knowledge.json"

    @property
    def progress_file(self) -> Path:
        return self.knowledge_dir / f"{self.book_key}_progress.json"

    @property
    def status_file(self) -> Path:
        return self.knowledge_dir / f"{self.book_key}_status.json"


class PageContent(BaseModel):
    has_content: bool
    knowledge: list[str]


# --- T4: Atomic file write helpers ---

def atomic_write_json(path: Path, data):
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(str(tmp), str(path))


def atomic_write_text(path: Path, content: str):
    tmp = path.with_suffix('.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(content)
    os.replace(str(tmp), str(path))


# --- Local skip heuristic (avoids API call for obvious non-content) ---

import re

_SKIP_PATTERNS = re.compile(
    r"(?:copyright|all rights reserved|isbn[\s\-]?\d|奥付|発行所|printed in japan)",
    re.IGNORECASE,
)


def should_skip_locally(page_text: str) -> bool:
    """Return True if the page is obviously non-content and can be skipped without an API call."""
    stripped = page_text.strip()
    if len(stripped) < 20:
        return True
    if _SKIP_PATTERNS.search(stripped) and len(stripped) < 300:
        return True
    return False


# --- T1: API retry helper with response guard ---

def call_api(client: anthropic.Anthropic, *, max_retries: int = 3, **kwargs) -> str:
    for attempt in range(max_retries):
        try:
            message = client.messages.create(**kwargs)
            if not message.content or message.content[0].type != "text":
                raise ValueError("Empty or non-text response from API")
            return message.content[0].text
        except (anthropic.APIError, anthropic.APIConnectionError,
                anthropic.RateLimitError, ValueError) as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** (attempt + 1)
            print(colored(f"  API error: {e}, retrying in {wait}s...", "yellow"))
            time.sleep(wait)


def create_client() -> anthropic.Anthropic:
    api_key = os.environ.get("ZAI_API_KEY")
    if not api_key:
        raise RuntimeError("ZAI_API_KEY is not set")
    return anthropic.Anthropic(api_key=api_key, base_url=ZAI_BASE_URL)


def save_knowledge_base(knowledge_base: list[str], config: BookConfig):
    atomic_write_json(config.knowledge_file, {"knowledge": knowledge_base})


# --- T2: Parse retry with failed-page tracking ---

def process_page(client: anthropic.Anthropic, page_text: str, knowledge: list[str], page_num: int, config: BookConfig) -> list[str] | None:
    """Process a single page. Returns updated knowledge list, or None if all parse retries failed."""
    if should_skip_locally(page_text):
        print(colored(f"  Skipping page {page_num + 1} (local heuristic)", "yellow"))
        return knowledge

    print(colored(f"\nProcessing page {page_num + 1}...", "yellow"))

    max_parse_retries = 3
    for attempt in range(max_parse_retries):
        try:
            raw_text = call_api(
                client,
                model=config.model,
                max_tokens=2048,
                system=SYSTEM_PROMPT_EXTRACT + '\n\nRespond ONLY with valid JSON matching this schema: {"has_content": bool, "knowledge": [str]}',
                messages=[{"role": "user", "content": f"Page text: {page_text}"}],
            )
        except Exception as e:
            print(colored(f"  API failed (page {page_num + 1}): {e}", "red"))
            return None

        try:
            raw = raw_text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            result = PageContent(**json.loads(raw))
            break
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            if attempt == max_parse_retries - 1:
                print(colored(f"  Parse failed after {max_parse_retries} attempts (page {page_num + 1}): {e}", "red"))
                return None
            print(colored(f"  Parse error (page {page_num + 1}, attempt {attempt + 1}): {e}, retrying...", "yellow"))

    if result.has_content:
        print(colored(f"  Found {len(result.knowledge)} new knowledge points", "green"))
        knowledge.extend(result.knowledge)
    else:
        print(colored("  Skipping page (no relevant content)", "yellow"))

    return knowledge


def load_existing_knowledge(config: BookConfig) -> list[str]:
    if config.knowledge_file.exists():
        print(colored("Loading existing knowledge base...", "cyan"))
        with open(config.knowledge_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(colored(f"  Loaded {len(data['knowledge'])} existing knowledge points", "green"))
            return data['knowledge']
    print(colored("Starting with fresh knowledge base", "cyan"))
    return []


def analyze_knowledge_base(client: anthropic.Anthropic, knowledge_base: list[str], config: BookConfig) -> str:
    if not knowledge_base:
        print(colored("\nSkipping analysis: No knowledge points collected", "yellow"))
        return ""

    print(colored("\nGenerating book analysis...", "cyan"))
    text = call_api(
        client,
        model=config.analysis_model,
        max_tokens=4096,
        system=SYSTEM_PROMPT_ANALYSIS,
        messages=[{"role": "user", "content": "Analyze this content:\n" + "\n".join(knowledge_base)}],
    )
    print(colored("Analysis generated successfully!", "green"))
    return text


def ensure_directories(config: BookConfig):
    for d in [config.pdf_dir, config.knowledge_dir, config.summaries_dir]:
        d.mkdir(parents=True, exist_ok=True)


def save_summary(summary: str, config: BookConfig, is_final: bool = False):
    if not summary:
        return

    kind = "final" if is_final else "interval"
    existing = list(config.summaries_dir.glob(f"{config.book_key}_{kind}_*.md"))
    next_number = max((int(f.stem.rsplit("_", 1)[1]) for f in existing), default=0) + 1
    summary_path = config.summaries_dir / f"{config.book_key}_{kind}_{next_number:03d}.md"

    markdown_content = f"""# Book Analysis: {config.book_key}
Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

{summary}

---
*Analysis generated using AI Book Analysis Tool (GLM 5.1)*
"""

    print(colored(f"\nSaving {kind} analysis to markdown...", "cyan"))
    atomic_write_text(summary_path, markdown_content)
    print(colored(f"  Analysis saved to: {summary_path}", "green"))


# --- T3: Status manifest ---

def load_status(config: BookConfig) -> dict:
    if config.status_file.exists():
        with open(config.status_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "book_key": config.book_key,
        "pdf_pages": 0,
        "processed_pages": 0,
        "test_mode": config.test_pages is not None,
        "pages_extracted": False,
        "summary_generated": False,
        "failed_pages": [],
        "completed_at": None,
    }


def save_status(status: dict, config: BookConfig):
    atomic_write_json(config.status_file, status)


# --- T6: PDF collision detection ---

def resolve_pdf_destination(config: BookConfig) -> Path:
    """Copy source PDF to pdf_dir, handling same-stem collisions."""
    dest_pdf = config.pdf_dir / config.pdf_path.name
    if dest_pdf.exists():
        if dest_pdf.stat().st_size != config.pdf_path.stat().st_size:
            h = hashlib.md5(config.pdf_path.read_bytes()).hexdigest()[:8]
            config.book_key_override = f"{config.pdf_path.stem}_{h}"
            dest_pdf = config.pdf_dir / f"{config.book_key}.pdf"
    if not dest_pdf.exists():
        shutil.copy2(config.pdf_path, dest_pdf)
    return dest_pdf


def process_book(client: anthropic.Anthropic, config: BookConfig):
    """Main processing loop for a single book."""
    ensure_directories(config)
    dest_pdf = resolve_pdf_destination(config)

    status = load_status(config)
    knowledge_base = load_existing_knowledge(config)
    failed_pages: list[int] = status.get("failed_pages", [])

    # Resume support
    start_page = config.start_page
    if config.progress_file.exists():
        with open(config.progress_file, 'r') as f:
            progress = json.load(f)
            start_page = max(start_page, progress.get("last_page", 0))
        if start_page > 0:
            print(colored(f"  Resuming from page {start_page + 1}", "yellow"))

    # T5: Track last analyzed index for interval delta
    last_analyzed_idx = 0

    with fitz.open(dest_pdf) as pdf_document:
        pdf_total = pdf_document.page_count
        end_page = min(config.test_pages, pdf_total) if config.test_pages is not None else pdf_total

        status["pdf_pages"] = pdf_total
        status["test_mode"] = config.test_pages is not None

        print(colored(f"\nProcessing {end_page} pages...", "cyan"))
        for page_num in range(start_page, end_page):
            page_text = pdf_document[page_num].get_text()
            result = process_page(client, page_text, knowledge_base, page_num, config)

            if result is None:
                failed_pages.append(page_num)
                print(colored(f"  Page {page_num + 1} recorded as failed", "red"))
            else:
                knowledge_base = result

            # Periodic save
            if (page_num + 1) % SAVE_INTERVAL == 0 or page_num + 1 == end_page:
                save_knowledge_base(knowledge_base, config)
                atomic_write_json(config.progress_file, {"last_page": page_num + 1, "total_pages": end_page})
                status["processed_pages"] = page_num + 1
                status["failed_pages"] = failed_pages
                save_status(status, config)

            # T5: Interval analysis with delta
            if config.analysis_interval:
                is_interval = (page_num + 1) % config.analysis_interval == 0
                is_final = page_num + 1 == end_page
                if is_interval and not is_final:
                    print(colored(f"\n  Progress: {page_num + 1}/{end_page}", "cyan"))
                    delta = knowledge_base[last_analyzed_idx:]
                    summary = analyze_knowledge_base(client, delta, config)
                    save_summary(summary, config, is_final=False)
                    last_analyzed_idx = len(knowledge_base)

            # Final analysis
            if page_num + 1 == end_page:
                print(colored(f"\n  Final page ({end_page}/{end_page})", "cyan"))
                status["pages_extracted"] = True
                save_status(status, config)

                summary = analyze_knowledge_base(client, knowledge_base, config)
                save_summary(summary, config, is_final=True)

                # T3: Mark complete ONLY after summary succeeds
                status["summary_generated"] = True
                status["completed_at"] = datetime.now().isoformat()
                save_status(status, config)

    # Cleanup progress file only after full completion
    if config.progress_file.exists():
        config.progress_file.unlink()

    print(colored("\nProcessing complete!", "green", attrs=['bold']))
    if failed_pages:
        print(colored(f"  Warning: {len(failed_pages)} pages failed: {failed_pages}", "yellow"))


def main():
    print(colored("""
PDF Book Analysis Tool (GLM 5.1)
---------------------------
Place your PDF in the same directory, then update PDF_NAME below.
Press Enter to continue or Ctrl+C to exit...
""", "cyan"))
    try:
        input()
    except KeyboardInterrupt:
        print(colored("\nCancelled.", "red"))
        return

    pdf_name = "meditations.pdf"
    config = BookConfig(pdf_path=Path(pdf_name), test_pages=60)
    client = create_client()
    process_book(client, config)


if __name__ == "__main__":
    main()
