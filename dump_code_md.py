import os
from pathlib import Path

output_file = "code_dump.md"
exclude_dirs = {".venv", "__pycache__", ".git", "data", "logs", "chrome_profile", "test"}
exclude_ext = {".pyc", ".db", ".log", ".exe", ".png", ".jpg"}

with open(output_file, "w", encoding="utf-8") as out:
    for root, dirs, files in os.walk("."):
        dirs[:] = sorted([d for d in dirs if d not in exclude_dirs])
        for file in sorted(files):
            path = Path(root) / file
            if path.suffix in exclude_ext:
                continue
            if file == output_file or file == "dump_code.py":
                continue
            # Берём только .py, .txt, .md, .env.example
            if path.suffix not in {".py", ".txt", ".md"} and file != ".env.example":
                continue
            rel_path = path.as_posix().lstrip("./")
            out.write(f"\n## {rel_path}\n\n```python\n")
            try:
                with open(path, "r", encoding="utf-8") as f:
                    out.write(f.read())
            except Exception as e:
                out.write(f"# Ошибка чтения: {e}\n")
            out.write("\n```\n")

print(f"✅ Готово! Файл: {output_file}")