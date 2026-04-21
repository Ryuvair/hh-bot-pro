# dump_code.py
import os
from pathlib import Path

output_file = "code_dump.txt"
exclude_dirs = {".venv", "__pycache__", ".git", "data", "logs", "chrome_profile"}
exclude_ext = {".pyc", ".db", ".log"}

with open(output_file, "w", encoding="utf-8") as out:
    for root, dirs, files in os.walk("."):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if Path(file).suffix in exclude_ext:
                continue
            if file == output_file:
                continue
            path = Path(root) / file
            if path.suffix == ".py" or file in ["requirements.txt", ".env.example"]:
                out.write(f"\n{'='*60}\n{path}\n{'='*60}\n")
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        out.write(f.read())
                except Exception as e:
                    out.write(f"Error reading file: {e}\n")