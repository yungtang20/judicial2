from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw"
DATABASE_PATH = ROOT / "judicial2_laws.sqlite3"
VERIFICATION_DATE = "2026-10-09"
STATUS = "待人工核定"


@dataclass(frozen=True)
class LawSource:
    filename: str
    article_no: str
    source_command: str
    expected_sha256: str
    paragraph_line_counts: tuple[int, ...]


SOURCES = (
    LawSource(
        filename="criminal_code_319-1.txt",
        article_no="刑法第 319 條之 1",
        source_command="twlegalrag law 刑法 319-1",
        expected_sha256="84C0CBC152809034107D7EB9F5C2FA6DB8C0D81108BC003857DD965612F10CD1",
        paragraph_line_counts=(2, 2, 2, 1),
    ),
    LawSource(
        filename="criminal_code_319-6.txt",
        article_no="刑法第 319 條之 6",
        source_command="twlegalrag law 刑法 319-6",
        expected_sha256="4D3AD96EAA3CD5A5CBE7CDA3C1FFD0AF4F40CB16802C983BA1585E473E0BA2C2",
        paragraph_line_counts=(2,),
    ),
    LawSource(
        filename="criminal_code_80.txt",
        article_no="刑法第 80 條",
        source_command="twlegalrag law 刑法 80",
        expected_sha256="48660D1338118EAC2CE2F85C5DA5940684EEA077B5129609E2135207706B1A92",
        paragraph_line_counts=(1, 2, 1, 1, 1, 1, 3),
    ),
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def panel_content_lines(raw_text: str) -> list[str]:
    lines = raw_text.splitlines()
    try:
        top = next(index for index, line in enumerate(lines) if line.startswith("┌"))
        bottom = next(index for index, line in enumerate(lines[top + 1 :], top + 1) if line.startswith("└"))
    except StopIteration as exc:
        raise ValueError("raw 輸出缺少終端機表格框線") from exc

    content: list[str] = []
    for line in lines[top + 1 : bottom]:
        if not (line.startswith("│") and line.endswith("│")):
            raise ValueError("raw 表格內含無法識別的行")
        value = line[1:-1]
        if value.startswith(" "):
            value = value[1:]
        value = value.rstrip()
        if value.startswith("層級:"):
            break
        if not value:
            break
        content.append(value)
    if not content:
        raise ValueError("raw 輸出未取得法條正文")
    return content


def join_paragraphs(lines: list[str], counts: tuple[int, ...]) -> str:
    if sum(counts) != len(lines):
        raise ValueError(f"正文顯示行數不符：預期 {sum(counts)}，實際 {len(lines)}")
    paragraphs: list[str] = []
    offset = 0
    for count in counts:
        paragraphs.append("".join(lines[offset : offset + count]))
        offset += count
    return "\n".join(paragraphs)


def metadata(raw_text: str) -> tuple[str, str, str]:
    url_match = re.search(r"全國法規資料庫:\s*(https://\S+)", raw_text)
    version_match = re.search(r"（(\d{4}-\d{2}-\d{2})）版", raw_text)
    modified_match = re.search(r"最後修正:\s*(\d{4}-\d{2}-\d{2})", raw_text)
    if not (url_match and version_match and modified_match):
        raise ValueError("raw 輸出缺少來源網址、資料版本或最後修正日期")
    return url_match.group(1), version_match.group(1), modified_match.group(1)


def load_rows() -> list[tuple[str, ...]]:
    rows: list[tuple[str, ...]] = []
    for source in SOURCES:
        path = (RAW_DIR / source.filename).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"缺少 raw 檔：{path}")
        actual_sha256 = sha256(path)
        if actual_sha256 != source.expected_sha256:
            raise ValueError(
                f"raw SHA-256 不符：{source.filename}，"
                f"預期 {source.expected_sha256}，實際 {actual_sha256}"
            )
        raw_text = path.read_text(encoding="utf-8")
        article_text = join_paragraphs(
            panel_content_lines(raw_text), source.paragraph_line_counts
        )
        source_url, dataset_version, last_modified_date = metadata(raw_text)
        rows.append(
            (
                source.article_no,
                article_text,
                source.source_command,
                source_url,
                dataset_version,
                VERIFICATION_DATE,
                last_modified_date,
                STATUS,
                "",
                str(path.relative_to(ROOT.parent)),
                actual_sha256,
            )
        )
    return rows


def build_database() -> None:
    rows = load_rows()
    if len(rows) != 3:
        raise ValueError(f"法條筆數不符：預期 3，實際 {len(rows)}")

    temporary_path = DATABASE_PATH.with_suffix(".sqlite3.tmp")
    if temporary_path.exists():
        temporary_path.unlink()
    try:
        connection = sqlite3.connect(temporary_path)
        try:
            connection.execute(
                """
                CREATE TABLE laws (
                    article_no TEXT PRIMARY KEY,
                    article_text TEXT NOT NULL,
                    source_command TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    dataset_version TEXT NOT NULL,
                    verification_date TEXT NOT NULL,
                    last_modified_date TEXT NOT NULL,
                    status TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    raw_path TEXT NOT NULL,
                    raw_sha256 TEXT NOT NULL
                )
                """
            )
            connection.executemany(
                """
                INSERT INTO laws (
                    article_no, article_text, source_command, source_url,
                    dataset_version, verification_date, last_modified_date,
                    status, notes, raw_path, raw_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            count = connection.execute("SELECT COUNT(*) FROM laws").fetchone()[0]
            if count != 3:
                raise ValueError(f"SQLite 筆數不符：預期 3，實際 {count}")
            connection.commit()
        finally:
            connection.close()
        temporary_path.replace(DATABASE_PATH)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


if __name__ == "__main__":
    build_database()
