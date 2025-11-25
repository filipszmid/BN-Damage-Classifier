import os
import shutil
from pathlib import Path

from PIL import Image

from src.config import get_project_root


def move_report_from_tests_to_logs(report_name: str, shipowner, source_dir: str = "tests/", ) -> None:
    src_file = os.path.join(get_project_root(), source_dir + report_name)
    dest_dir = os.path.join(get_project_root(), "data", shipowner, "logs/reports")
    dest_file = Path(dest_dir) / Path(src_file).name

    os.makedirs(dest_dir, exist_ok=True)

    try:
        shutil.copy(src=src_file, dst=dest_file)
        print(f"File copied to {dest_file}")
        return dest_file
    except Exception as e:
        print(f"Failed to copy file: {e}")
        exit(1)


def open_image(img_path):
    img = Image.open(img_path)

    # Define the size for resizing - adjust these values as needed
    base_width = 800
    w_percent = (base_width / float(img.size[0]))
    h_size = int((float(img.size[1]) * float(w_percent)))

    # Resize the image while maintaining the aspect ratio
    img_resized = img.resize((base_width, h_size), Image.LANCZOS)

    # Display the resized image in Jupyter Notebook
    img_resized.show()
