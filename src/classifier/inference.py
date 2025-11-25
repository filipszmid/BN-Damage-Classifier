import json
import os

import pandas as pd
import torch
from PIL import Image
from loguru import logger
from torchvision import transforms

from src.classifier.model import ResNetClassifier
from src.classifier.utils import load_json
from src.parser.utils import open_image


class SingletonMeta(type):
    """
    A Singleton metaclass that ensures a class has only one instance and provides a global point of access to it.
    """

    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            instance = super().__call__(*args, **kwargs)
            cls._instances[cls] = instance
        return cls._instances[cls]


class ContainerDamageClassifierWorkflow(metaclass=SingletonMeta):
    """
    A workflow class for classifying container damage using a pre-trained model.

    Attributes:
        device (torch.device): Device configuration, either CUDA or CPU.
        mappings (dict): Dictionary of mappings from categorical labels to indices.
        model (ResNetClassifier): The neural network model used for predictions.
        transform (transforms.Compose): Transformation operations for input images.
    """

    def __init__(self, db, run_name: str, checkpoint_id: int):
        """
        Initializes the classifier with model parameters and category mappings.

        Args:
            run_name (str): Name of a run.
            checkpoint_id (str): Name of existing checkpoint.
        """
        self.db = db
        run_path = os.path.join("../../data/cma/model/", run_name)
        model_path = os.path.join(
            run_path, "checkpoints", f"model_epoch_{checkpoint_id}.pth"
        )  # fold_3
        self.run_path = run_path
        self.model_path = model_path
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.mappings = load_json(os.path.join(run_path, "mappings.json"))
        num_classes_per_category = self.count_classes(self.mappings)
        self.model = ResNetClassifier(num_classes_per_category).to(self.device)
        checkpoint = torch.load(model_path, map_location=self.device)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()

        self.transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
                ),
            ]
        )

    def decode_prediction(self, predictions: torch.Tensor) -> dict:
        """
        Decodes model predictions into readable labels using mappings.

        Args:
            predictions (torch.Tensor): Output tensor from the model prediction.

        Returns:
            dict: A dictionary containing decoded category labels.
        """
        return {
            "location": self.mappings["location"][str(predictions[0].argmax().item())],
            "component": self.mappings["component"][
                str(predictions[1].argmax().item())
            ],
            "repair_type": self.mappings["repair_type"][
                str(predictions[2].argmax().item())
            ],
            "damage": self.mappings["damage"][str(predictions[3].argmax().item())],
        }

    def predict(self, image_path: str) -> dict:
        """
        Processes an image and predicts damage categories.

        Args:
            image_path (str): Path to the image file to predict.

        Returns:
            dict: Predicted category labels.
        """
        image = Image.open(image_path).convert("RGB")
        image = self.transform(image).unsqueeze(0).to(self.device)
        with torch.no_grad():
            predictions = self.model(image)
            # print(predictions)
            return self.decode_prediction(predictions)

    def sample_and_predict(self) -> dict:
        """
        Samples an image from a CSV file and makes a prediction.

        Returns:
            dict: Predicted category labels.
        """
        val_data_path = os.path.join(self.run_path, "val_data.csv")  # fold_3/
        data = pd.read_csv(val_data_path)
        sample_row = data.sample(1).iloc[0]
        metadata = json.loads(sample_row["metadata"])

        keys_to_include = ["location", "component", "repair_type", "damage"]
        subset_log = {k: metadata[k] for k in keys_to_include}

        logger.info(f"Metadata:{subset_log}")

        image_path = sample_row["processed_row"]
        prediction = self.predict(image_path)
        open_image(image_path)
        return prediction

    def predict_repairs(self, file_paths, pipeline_timestamp) -> list:
        """
        Predicts report.

        Returns:
            dict: Predicted category labels.
        """
        predictions = []
        for path in file_paths:
            prediction = self.predict(path)
            # prediction_rename = {
            #     "lokalizacja": prediction["location"],
            #     "komponent": prediction["component"],
            #     "uszkodzenie": prediction["damage"],
            #     "rodzaj naprawy": prediction["repair_type"],
            # }
            # Always none, not enough data to predict these
            prediction["length"] = None
            prediction["width"] = None
            prediction["quantity"] = None
            predictions.append(prediction)
        logger.success("Own model predictions:")
        logger.success(predictions)
        self.db["reports"].update_one(
            {"pipeline_timestamp": pipeline_timestamp},
            {"$set": {"own_model_predictions": predictions}},
        )
        return predictions

    def count_classes(self, mappings: dict) -> dict:
        """
        Counts the number of unique classes per category from mappings.

        Args:
            mappings (dict): Category mappings from labels to indices.

        Returns:
            dict: A dictionary with the number of classes per category.
        """
        return {category: len(values) for category, values in mappings.items()}


if __name__ == "__main__":
    # run_name = "run_20240730-210406"
    # run_name = "run_20240807-152905_paranephritis"  # 8
    run_name = "run_20240809-185823_crony"
    run_name = "run_20240810-010935_akhrot"  # FOLD 3 - 0.1 val loss
    run_name = "run_20240823-014941_grindable"

    damage_classifier = ContainerDamageClassifierWorkflow(
        run_name=run_name, checkpoint_id=6
    )
    prediction = damage_classifier.sample_and_predict()
    logger.success(f"Prediction:{prediction}")
