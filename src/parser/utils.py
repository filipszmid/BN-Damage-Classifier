import os
import os
import shutil
from pathlib import Path

from src.config import get_project_root


def move_report_from_tests_to_logs(report_name: str) -> None:
    src_file = os.path.join(get_project_root(), "tests/" + report_name)
    dest_dir = os.path.join(get_project_root(), "logs/reports")
    dest_file = Path(dest_dir) / Path(src_file).name

    os.makedirs(dest_dir, exist_ok=True)

    try:
        shutil.copy(src=src_file, dst=dest_file)
        print(f"File copied to {dest_file}")
    except Exception as e:
        print(f"Failed to copy file: {e}")
        exit(1)