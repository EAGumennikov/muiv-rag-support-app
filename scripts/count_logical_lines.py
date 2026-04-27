from __future__ import annotations

"""
Подсчет логических строк кода учебного web-сервиса.

Скрипт нужен для ревизии требования по объему программной реализации.
Он учитывает только исходный код приложения, шаблоны и статические ресурсы,
исключая документацию, виртуальное окружение, git-служебные файлы, runtime-
артефакты, индексы, embeddings и пользовательские выгрузки.
"""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# В подсчет входят только собственные исходные файлы проекта.
INCLUDED_PATHS = [
    PROJECT_ROOT / "app.py",
    PROJECT_ROOT / "db",
    PROJECT_ROOT / "services",
    PROJECT_ROOT / "scripts",
    PROJECT_ROOT / "templates",
    PROJECT_ROOT / "static" / "css",
    PROJECT_ROOT / "static" / "js",
]

INCLUDED_EXTENSIONS = {".py", ".html", ".css", ".js"}
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    "input",
    "output",
    "logs",
    "docs",
}

SIMPLE_COMMENT_PREFIXES = {
    ".py": ("#",),
    ".css": ("/*", "*", "*/"),
    ".js": ("//",),
    ".html": ("<!--", "-->"),
}


def iter_source_files() -> list[Path]:
    # Runtime-каталоги и внешние библиотеки исключаются, потому что они не
    # отражают объем собственной программной реализации web-сервиса.
    files: list[Path] = []
    for path in INCLUDED_PATHS:
        if path.is_file() and path.suffix in INCLUDED_EXTENSIONS:
            files.append(path)
            continue
        if not path.is_dir():
            continue
        for candidate in path.rglob("*"):
            if not candidate.is_file() or candidate.suffix not in INCLUDED_EXTENSIONS:
                continue
            if any(part in EXCLUDED_DIRS for part in candidate.relative_to(PROJECT_ROOT).parts):
                continue
            files.append(candidate)
    return sorted(files)


def is_logical_line(line: str, suffix: str) -> bool:
    # Логической считается непустая строка, которая не является простой
    # однострочной строкой комментария для соответствующего типа файла.
    stripped = line.strip()
    if not stripped:
        return False
    return not any(stripped.startswith(prefix) for prefix in SIMPLE_COMMENT_PREFIXES.get(suffix, ()))


def count_file(path: Path) -> int:
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if is_logical_line(line, path.suffix):
            count += 1
    return count


def main() -> None:
    totals_by_extension: dict[str, int] = {}
    totals_by_group: dict[str, int] = {}
    total = 0

    for path in iter_source_files():
        count = count_file(path)
        relative = path.relative_to(PROJECT_ROOT)
        group = relative.parts[0] if len(relative.parts) > 1 else str(relative)
        totals_by_extension[path.suffix] = totals_by_extension.get(path.suffix, 0) + count
        totals_by_group[group] = totals_by_group.get(group, 0) + count
        total += count

    print("Логические строки по расширениям:")
    for suffix, count in sorted(totals_by_extension.items()):
        print(f"{suffix}: {count}")

    print("\nЛогические строки по группам:")
    for group, count in sorted(totals_by_group.items()):
        print(f"{group}: {count}")

    print(f"\nИтого логических строк: {total}")


if __name__ == "__main__":
    main()
