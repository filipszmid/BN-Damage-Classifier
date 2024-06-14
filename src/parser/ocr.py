import math
import os
import re
from datetime import datetime
from typing import List, Tuple

from PIL import Image, ImageDraw
from dotenv import load_dotenv
from google.cloud import vision
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from loguru import logger

from src.config import get_project_root
from src.parser.utils import move_report_from_tests_to_logs

load_dotenv()


class OCRWorkflow:
    """
    Manages OCR operations using Google Vision API, including detecting text within images,
    drawing boxes around detected text, and saving annotated and cropped versions of images.
    """

    SCOPES: List[str] = ["https://www.googleapis.com/auth/cloud-vision"]
    LETTER_MAP: dict = {
        "F": ["G", "B", "T", "H", "X"],
        "D": ["G", "B", "T", "H", "X"],
        "L": ["G", "B", "T", "H", "X"],
        "R": ["G", "B", "T", "H", "X"],
        "X": ["X"],
        "I": ["X"],
        "T": ["L", "R", "X"],
        "U": ["L", "R", "X"],
        "B": ["L", "R", "X"],
    }
    BOX_WIDTH: int = 1000
    BOX_HEIGHT: int = 1000
    PROJECT_ROOT = get_project_root()

    def __init__(self, report_name: str) -> None:
        """
        Initializes directories, credentials, and logging settings.

        Args:
        report_name (str): Name of the report file to process.
        """
        self.reports_dir = os.path.join(self.PROJECT_ROOT, "logs/reports/") # TODO: to delete redundant
        self.report_name = report_name
        self.report_name_no_extension, self.extension = report_name.split(".")
        self.credentials = self._get_credentials()
        self.vision_client = vision.ImageAnnotatorClient(credentials=self.credentials)
        self.report_ocr_dir = os.path.join(self.PROJECT_ROOT, "logs/report_ocr_boxes/")
        self.raw_report_dir = os.path.join(self.PROJECT_ROOT, "logs/reports/")
        self.processed_rows_dir = os.path.join(self.PROJECT_ROOT, "logs/processed_rows/")
        self.raw_processed_dir = os.path.join(self.PROJECT_ROOT, "logs/raw_processed_rows/")
        self.annotation_log_dir = os.path.join(self.PROJECT_ROOT, "logs/img_annotations/")
        os.makedirs(self.report_ocr_dir, exist_ok=True)
        os.makedirs(self.raw_report_dir, exist_ok=True)
        os.makedirs(self.processed_rows_dir, exist_ok=True)
        os.makedirs(self.raw_processed_dir, exist_ok=True)
        os.makedirs(self.annotation_log_dir, exist_ok=True)
        self.pipeline_timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:17]
        logger.info(f"Initialized OCR workflow for {self.report_name} \n Pipeline timestamp: {self.pipeline_timestamp}")

    def _get_credentials(self) -> Credentials:
        """
        Retrieves or generates new Google Cloud credentials.

        Returns:
        Credentials: The authenticated credentials for Google Cloud.
        """
        creds_file = os.path.join(self.PROJECT_ROOT, "token.json")
        client_secret_file = os.path.join(self.PROJECT_ROOT,"client_secret.json") #TODO: crashuje na tym, inna sciezka?
        logger.success(creds_file)
        logger.success(client_secret_file)
        if os.path.exists(creds_file):
            creds = Credentials.from_authorized_user_file(
                creds_file, scopes=self.SCOPES
            )
            logger.info("App authenticated, using token.")
        else:
            logger.warning("No token found, app need to be authenticated")
            flow = InstalledAppFlow.from_client_secrets_file(
                client_secret_file, scopes=self.SCOPES
            )
            creds = flow.run_local_server(port=0)
            with open(creds_file, "w") as token:
                token.write(creds.to_json())
            logger.info("App authenticated. Token saved.")
        return creds

    def detect_text(self) -> vision.AnnotateImageResponse:
        """
        Performs text detection on the specified image file.

        Returns:
        vision.AnnotateImageResponse: The response from the Google Vision API containing text detection results.
        """
        path = os.path.join(self.reports_dir, self.report_name)
        with open(path, "rb") as image_file:
            content = image_file.read()
        image = vision.Image(content=content)
        response = self.vision_client.document_text_detection(image=image)
        self._save_response_annotations(response)
        logger.success("Text detection completed for {}".format(self.report_name))
        return response

    def _save_response_annotations(
        self, response: vision.AnnotateImageResponse
    ) -> None:
        """
        Saves the response from the Google Vision API to a text file.

        Args:
        response (vision.AnnotateImageResponse): The response containing text annotations.
        """
        filename = f"{self.pipeline_timestamp}-{self.report_name_no_extension}.txt"
        filepath = os.path.join(self.annotation_log_dir, filename)
        with open(filepath, "w") as file:
            file.write(str(response))
        logger.info(f"Saved response annotations to {filepath}")

    def _center_image_on_fixed_canvas(
        self, file_path: str, code: str, canvas_width: int, canvas_height: int
    ) -> None:
        """
        Centers an image on a white canvas of specified dimensions and saves it to a new file.

        Args:
            file_path (str): The path to the original image file.
            code (str): An identifier or code associated with the image, used in naming the output file.
            canvas_width (int): The width of the canvas on which to center the image.
            canvas_height (int): The height of the canvas on which to center the image.
        """
        file_path_white_bg = f"{self.processed_rows_dir}{self.pipeline_timestamp}-{self.report_name_no_extension}-{code}.png"
        with Image.open(file_path) as img:
            # Create a new white background image of the fixed dimensions
            background = Image.new("RGB", (canvas_width, canvas_height), "white")

            # Calculate positioning to center the image on the white background
            left = (canvas_width - img.width) // 2
            top = (canvas_height - img.height) // 2

            # Paste the original image onto the white background at calculated position
            background.paste(img, (left, top))

            # Save the final image back to the same file or to a new file if preferred
            background.save(file_path_white_bg)

    def run_ocr_pipeline(
        self, response: vision.AnnotateImageResponse
    ) -> str:
        """
        Draws bounding boxes around detected text and saves annotated images.

        Args:
        response (vision.AnnotateImageResponse): The response containing text annotations.
        """
        image_path = self.reports_dir + self.report_name
        img = Image.open(image_path)
        img.save(f"{self.raw_report_dir}{self.pipeline_timestamp}-{self.report_name}")
        draw_img = img.copy()  # Create a copy for drawing
        draw = ImageDraw.Draw(draw_img)

        pattern = self._generate_regex_pattern(self.LETTER_MAP)

        if response.text_annotations:
            for annotation in response.text_annotations[1:]:
                text = annotation.description
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    code = match.group(0)[
                        :4
                    ]  # Extract the code (first four characters of the match)
                    logger.debug(f"Recognized code: {code}")
                    vertices = [
                        (vertex.x, vertex.y)
                        for vertex in annotation.bounding_poly.vertices
                    ]
                    angle = self._calculate_rotation_angle(vertices)

                    # Calculate rectangle vertices and apply rotation
                    min_x = min(vertices, key=lambda v: v[0])[0]
                    min_y = min(vertices, key=lambda v: v[1])[1]
                    max_y = max(vertices, key=lambda v: v[1])[1]
                    extended_corners = [
                        (min_x, min_y),
                        (min_x + self.BOX_WIDTH, min_y),
                        (min_x + self.BOX_WIDTH, max_y),
                        (min_x, max_y),
                    ]
                    rotated_corners = self._rotate_corners(
                        extended_corners, min_x, (min_y + max_y) / 2, angle
                    )

                    # Draw the rotated rectangle on the display image
                    draw.polygon(rotated_corners, outline="red")

                    # Crop and save the image based on the calculated bounding box using the original image
                    self._save_cropped_image(
                        img,
                        self.BOX_WIDTH,
                        self.BOX_HEIGHT,
                        rotated_corners,
                        code,
                        angle,
                    )
        draw_img.save(
            f"{self.report_ocr_dir}{self.pipeline_timestamp}-{self.report_name_no_extension}-OCR.png"
        )
        logger.success(f"Drawn OCR boxes on report {self.report_name_no_extension}\n Pipeline: {self.pipeline_timestamp}")
        return self.pipeline_timestamp
    @staticmethod
    def _generate_regex_pattern(letter_map: dict) -> str:
        """
        Generates a regex pattern for identifying specific letter combinations.

        Args:
        letter_map (dict): A dictionary specifying valid starting letters and their subsequent valid followers.

        Returns:
        str: A regex pattern built from the specified letter combinations.
        """
        parts = []
        for letter, followers in letter_map.items():
            for follower in followers:
                parts.append(f"{letter}{follower}")
        pattern = "|".join([rf"\b{part}\w*\b" for part in parts])
        return pattern

    @staticmethod
    def _calculate_rotation_angle(vertices: List[Tuple[int, int]]) -> float:
        """
        Calculates the rotation angle of a text box based on its vertices.

        Args:
        vertices (List[Tuple[int, int]]): A list of tuples representing the vertices of the text box.

        Returns:
        float: The rotation angle in degrees.
        """
        if len(vertices) < 4:
            return 0
        p1, p2 = vertices[0], vertices[1]
        angle_rad = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        return math.degrees(angle_rad)

    @staticmethod
    def _rotate_corners(
        corners: List[Tuple[int, int]], cx: int, cy: int, angle_deg: float
    ) -> List[Tuple[float, float]]:
        """
        Rotates a list of corner points around a center point by a given angle.

        Args:
        corners (List[Tuple[int, int]]): The original corners of the box.
        cx (int): The x-coordinate of the center point for rotation.
        cy (int): The y-coordinate of the center point for rotation.
        angle_deg (float): The angle in degrees by which to rotate the corners.

        Returns:
        List[Tuple[int, int]]: A list of the rotated corner points.
        """
        angle_rad = math.radians(angle_deg)
        cos_theta = math.cos(angle_rad)
        sin_theta = math.sin(angle_rad)
        return [
            (
                cos_theta * (x - cx) - sin_theta * (y - cy) + cx,
                sin_theta * (x - cx) + cos_theta * (y - cy) + cy,
            )
            for x, y in corners
        ]

    def _save_cropped_image(
        self,
        img: Image.Image,
        box_width: int,
        box_height: int,
        corners: List[Tuple[int, int]],
        code: str,
        angle: float,
    ) -> None:
        """
        Crops and saves an image based on specified corners and rotation angle.

        Args:
        img (Image.Image): The original image from which to crop.
        box_width (int): The width of the box to crop around the text.
        box_height (int): The height of the box to crop around the text.
        corners (List[Tuple[int, int]]): The corners defining the area to crop.
        code (str): A specific code associated with the text.
        angle (float): The rotation angle to correct the text orientation.
        """
        file_path = f"{self.raw_processed_dir}{self.pipeline_timestamp}-{self.report_name_no_extension}-{code}.png"
        # Find bounding box for the rotated corners
        x_coords, y_coords = zip(*corners)
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)

        # Crop and rotate the image
        cropped_image = img.crop((min_x, min_y, max_x, max_y))
        rotated_cropped_image = cropped_image.rotate(
            -angle, expand=True, fillcolor="white"
        )  # Negative angle to correct orientation

        rotated_cropped_image.save(file_path)

        # resize_image_to_fixed_height(file_path, 500)
        self._center_image_on_fixed_canvas(file_path, code, box_width, box_height)


if __name__ == "__main__":
    report_name = "APZU3211393_418675_20231212_0747334299019332773351257.webp"
    move_report_from_tests_to_logs(report_name)
    workflow = OCRWorkflow(report_name)
    response = workflow.detect_text()
    workflow.run_ocr_pipeline(response)
