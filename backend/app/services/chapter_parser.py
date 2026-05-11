import re


CHAPTER_HEADING_RE = re.compile(
    r"(?im)^(?:chapter|ch\.?)\s+(\d+)(?:\s*[:.\-–—]\s*|\s+)?(.*)$"
)


def chapter_body_without_heading(content):
    lines = content.splitlines()

    if not lines:
        return ""

    return "\n".join(lines[1:]).strip()


def split_txt_into_chapters(text):
    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    matches = list(CHAPTER_HEADING_RE.finditer(normalized_text))

    if not matches:
        return [
            {
                "chapter_number": 1,
                "title": "Chapter 1",
                "content": normalized_text,
            }
        ]

    chapters = []
    accepted_matches = []
    expected_chapter_number = None

    for match in matches:
        chapter_number = int(match.group(1))

        if expected_chapter_number is None:
            expected_chapter_number = chapter_number

        if chapter_number != expected_chapter_number:
            continue

        accepted_matches.append(match)
        expected_chapter_number += 1

    for index, match in enumerate(accepted_matches):
        start = match.start()
        end = (
            accepted_matches[index + 1].start()
            if index + 1 < len(accepted_matches)
            else len(normalized_text)
        )
        chapter_number = int(match.group(1))

        title_suffix = match.group(2).strip()
        title = f"Chapter {chapter_number}"

        if title_suffix:
            title = f"{title}: {title_suffix}"

        content = normalized_text[start:end].strip()
        body = chapter_body_without_heading(content)

        if not body:
            continue

        chapters.append(
            {
                "chapter_number": chapter_number,
                "title": title,
                "content": content,
            }
        )

    return chapters
