"""Merge all markdown files under .agents into a single EPUB.

Each file is parsed individually (so unbalanced code fences in one file
cannot swallow content from the next), then the resulting chapters are
combined into one EPUB via the skill's EPUBGenerator.
"""
import re
import sys
from pathlib import Path

SCRIPTS = Path(r"C:\git_prive\WTChatbot\.agents\skills\markdown-to-epub-converter\scripts")
sys.path.insert(0, str(SCRIPTS))

from markdown_processor import MarkdownProcessor, EbookMetadata
from epub_generator import EPUBGenerator

AGENTS_DIR = Path(r"C:\git_prive\WTChatbot\.agents")
OUTPUT = Path(r"C:\git_prive\WTChatbot\agents-skills.epub")


def has_h1(content: str) -> bool:
    # Cheap check outside code blocks: strip fenced blocks first
    stripped = re.sub(r"```[^\n]*\n.*?```", "", content, flags=re.DOTALL)
    return re.search(r"^# ", stripped, re.MULTILINE) is not None


def build_chapters():
    all_chapters = []
    seen_titles = {}
    files = sorted(AGENTS_DIR.rglob("*.md"))
    for f in files:
        rel = f.relative_to(AGENTS_DIR)
        skill = rel.parts[-2] if len(rel.parts) >= 2 else "agents"
        content = f.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").strip()
        if not content:
            continue
        source_note = f"*Bron: `.agents/{rel.as_posix()}`*"
        if has_h1(content):
            work = content
        else:
            work = f"# {skill} — {rel.parts[-1]}\n\n{content}"

        result = MarkdownProcessor().process(work)
        chapters = result["chapters"]
        if not chapters:
            continue
        # Mark the first chapter of each file with its source path
        chapters[0].content = (source_note + "\n\n" + (chapters[0].content or "")).strip()

        for ch in chapters:
            # Deduplicate titles: identical titles break TOC linking/anchors
            if ch.title in seen_titles:
                seen_titles[ch.title] += 1
                ch.title = f"{ch.title} ({skill})"
                if ch.title in seen_titles:
                    ch.title = f"{ch.title} {seen_titles[ch.title]}"
            else:
                seen_titles[ch.title] = 1
            all_chapters.append(ch)
    return len(files), all_chapters


def main() -> None:
    n_files, chapters = build_chapters()
    print(f"Parsed {n_files} markdown files into {len(chapters)} chapters")
    metadata = EbookMetadata(
        title="WTChatbot — Agent Skills (.agents)",
        author="WTChatbot project",
        language="en",
    )
    ok = EPUBGenerator(metadata).generate(chapters, str(OUTPUT))
    print("EPUB written" if ok else "FAILED", "->", OUTPUT, OUTPUT.stat().st_size if ok else "")


if __name__ == "__main__":
    main()
