import os
import base64
import mimetypes
import json
import re

from loguru import logger
from dotenv import load_dotenv
from openai import OpenAI

from src.config import get_project_root
from src.parser.errors import WrongGPTAnswerError
from src.parser.pricer import PricerWorkflow
from src.parser.prompt import PROMPT_TEMPLATE_GET_REPAIRS_LIST

load_dotenv()


class RepairRecommenderWorkflow:
    """
    Manages the parsing of image files encoded in base64 and making recommendations using OpenAI.

    Attributes:
        openai_client (OpenAI): Client to interact with OpenAI's API.
        report_name_no_extension (str): Base name for report images to process.
        processed_rows_path (str): Path to directory containing images.
    """

    MODEL_VERSION = "gpt-4o-2024-05-13"
    PROJECT_ROOT = get_project_root()

    def __init__(
        self,
        report_name: str,
        pipeline_timestamp: str,
        container_type: str,
        openai_client: OpenAI = None,
        pricer_client: PricerWorkflow = None,
    ):
        """
        Initializes the workflow with paths and an optional OpenAI client.

        Parameters:
            report_name (str): The base name for the report images to identify relevant files.
            pipeline_timestamp (str): The unique pipeline timestamp.
            container_type (str): The type of container, used for filtering pricing data.
            openai_client (OpenAI, optional): A custom instance of the OpenAI client. Defaults to a new instance if not provided.
            pricer_client (PricerWorkflow, optional): A custom instance of the PricerWorkflow. Defaults to a new instance if not provided.
        """
        self.processed_rows_path = os.path.join(
            self.PROJECT_ROOT, "logs/processed_rows/"
        )
        self.gpt_labels_path = os.path.join(self.PROJECT_ROOT, "logs/gpt_labels/")
        self.report_name_no_extension = report_name.split(".")[0]
        self.pipeline_timestamp = pipeline_timestamp
        self.container_type = container_type
        self.openai_client = openai_client if openai_client is not None else OpenAI()
        self.pricer_client = (
            pricer_client if pricer_client is not None else PricerWorkflow()
        )

    def image_to_base64(self, image_path: str) -> str:
        """
        Converts an image file to a base64 encoded string suitable for transmission over HTTP.

        Parameters:
            image_path (str): The file system path to the image file to be converted.

        Returns:
            str: A base64 encoded string of the image file including the MIME type.
        """
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type or not mime_type.startswith("image"):
            raise ValueError("The file type is not recognized as an image")

        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode("utf-8")

        return f"data:{mime_type};base64,{encoded_string}"

    def get_files(self) -> list:
        """
        Retrieves a list of image file paths from the specified directory that match the report name.

        Returns:
            list: A list of full paths to the image files relevant to the current report.
        """
        files = []
        for filename in os.listdir(self.processed_rows_path):
            if filename.startswith(
                self.pipeline_timestamp + "-" + self.report_name_no_extension + "-"
            ) and filename.endswith(".png"):
                full_path = os.path.join(self.processed_rows_path, filename)
                files.append(full_path)
        logger.info(f"Read files for request: {files}")
        return files

    def construct_request(self, files: list) -> list:
        """
        Constructs a request payload containing text prompts and encoded images for the OpenAI API.

        Parameters:
            files (list): A list of file paths of images to include in the API request.

        Returns:
            list: A list of dictionaries representing the structured data for the API request.
        """
        codes, l1_list = self.extract_codes_and_first_letters()
        parts_hints = self.pricer_client.get_pricing_data(l1_list, self.container_type)

        logger.debug(f"Codes: {codes} First letters: {l1_list}\n")
        logger.debug(f"Part hints: {parts_hints.head()}")
        if parts_hints.empty:
            logger.warning(
                "Alert! No operations found. Probably wrong container type or components map."
            )

        prompt_text = PROMPT_TEMPLATE_GET_REPAIRS_LIST.format(
            codes=codes, parts_hints=parts_hints
        )
        content = [{"type": "text", "text": prompt_text}]
        for file_path in files:
            try:
                base64_string = self.image_to_base64(file_path)
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": base64_string, "detail": "high"},
                    }
                )
                logger.debug(f"File attached: {file_path}")
            except Exception as e:
                logger.error(f"Failed to process {file_path}: {e}")
        return content

    def _save_to_logs(self, json_response, pipeline_timestamp) -> None:
        """
        Saves a JSON response to a file in the specified directory with a filename based on the pipeline timestamp.

        Args:
            json_response (dict): The JSON response to be saved.
            pipeline_timestamp (str): A timestamp used to name the file uniquely.
        """
        file_path = os.path.join(self.gpt_labels_path, f"{pipeline_timestamp}.json")
        os.makedirs(self.gpt_labels_path, exist_ok=True)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(json_response, f, ensure_ascii=False, indent=4)
            logger.success(f"Response saved successfully to {file_path}")
        except Exception as e:
            logger.error(f"Failed to save response to log: {e}")

    def request_recommendations(self, content: list) -> dict:
        """
        Sends a request to the OpenAI API with the constructed content and returns the response.

        Parameters:
            content (list): A structured list of data including text and images prepared for the API request.

        Returns:
            dict: The parsed and structured response from the OpenAI API.
        """
        message = {"role": "user", "content": content}
        logger.info("Sending request to GPT...")
        response = self.openai_client.chat.completions.create(
            model=self.MODEL_VERSION, messages=[message], max_tokens=2300
        )
        logger.info(f"Raw response: {response.choices[0].message.content}")

        json_response = self._format_response(response.choices[0].message.content)
        self._save_to_logs(json_response, self.pipeline_timestamp)

        return json_response

    def extract_codes_and_first_letters(self) -> tuple:
        """
        Extracts unique codes and their first letters from filenames in a specified directory that match a given report prefix.

        Returns:
            tuple: A tuple containing two elements:
                1. A sorted list of unique codes extracted from the filenames.
                2. A sorted list of unique first letters of these codes.
        """
        # TODO: what if there will be 2 same codes for a given report and with different repairs?
        codes = set()
        first_letters = set()

        pattern = re.compile(
            re.escape(self.pipeline_timestamp + "-" + self.report_name_no_extension)
            + r"-(\w+)\.png"
        )

        for filename in os.listdir(self.processed_rows_path):
            match = pattern.match(filename)
            if match:
                code = match.group(1)
                codes.add(code)
                first_letters.add(code[0])

        return (sorted(codes), sorted(first_letters))

    @staticmethod
    def _format_response(response: str) -> dict:
        """Parse the JSON-formatted string response from GPT into a Python dictionary."""
        clean_str = re.sub(r"```json|```", "", response).strip()
        try:
            return json.loads(clean_str)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON from the response.")
            raise WrongGPTAnswerError from e

    def recommend_repairs(self):
        """
        Orchestrates the process to recommend repairs based on the images and context provided.

        Returns:
            dict: A dictionary containing the recommendations from the OpenAI API.
        """
        files = self.get_files()
        content = self.construct_request(files)
        response = self.request_recommendations(content)
        return response


if __name__ == "__main__":
    report_name, container_type = (
        "APZU3211393_418675_20231212_0747334299019332773351257.webp",
        "RF",
    )

    logger.info(
        f"Starting repair recommendation for report: {report_name}, OCR rows from: "
        f", and container type: {container_type}"
    )
    workflow = RepairRecommenderWorkflow(
        report_name=report_name,
        pipeline_timestamp="20240610231818",
        container_type=container_type,
    )
    logger.debug("Recommender initialized")
    recommendations = workflow.recommend_repairs()
    logger.success(recommendations)
