import json
import os
from hyperopt import hp, fmin, tpe, Trials, STATUS_OK
from typing import Dict, Any
from config import TrainConfig
from src.classifier.train import TrainWorkflow
from loguru import logger
import numpy as np


def convert_numpy(obj):
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj


class HyperparameterTuningWorkflow:
    """
    Class to perform hyperparameter tuning for a training workflow using Hyperopt.

    Attributes:
        max_evals (int): Maximum number of evaluations during the hyperparameter optimization.
        space (Dict[str, Any]): The space over which to search hyperparameters.
        trials (Trials): Object to store details of each iteration.
    """

    def __init__(self, max_evals: int = 50) -> None:
        """
        Initializes the hyperparameter tuning workflow with a defined space and number of evaluations.

        Args:
            max_evals (int): Maximum number of evaluations to perform. Defaults to 50.
        """
        self.space = {
            "metadata_file": "../../data/metadata_reports_1.json",
            "data_path": "../../data/row_map_dataset.csv",
            "with_augmentation": hp.choice("with_augmentation", [False, True]),
            "num_epochs": 10,
            "resume_run": None,
            "learning_rate": hp.choice("learning_rate", [0.1, 0.001, 0.0001]),
            "batch_size": hp.choice("batch_size", [8, 16, 64]),
            "dropout_rate": hp.uniform("dropout_rate", 0.0, 0.5),
            'weight_decay': hp.choice('weight_decay', [0, hp.loguniform('log_weight_decay', -23, -6.9)])
        }

        self.max_evals = max_evals
        self.trials = Trials()

    def objective(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Objective function for the hyperparameter search, evaluated by Hyperopt.

        Args:
            params (Dict[str, Any]): Dictionary containing one set of parameters from the search space.

        Returns:
            Dict[str, Any]: A dictionary with keys 'loss' and 'status', where 'loss' is the metric to minimize.
        """
        config = TrainConfig(**params)
        logger.info(f"Starting training with hyperparameters: {config}")
        workflow = TrainWorkflow(config)
        workflow.prepare_data()
        loss = workflow.train_model()

        run_path = workflow.base_path
        os.makedirs(run_path, exist_ok=True)
        with open(os.path.join(run_path, "final_loss.json"), "w") as f:
            json.dump({"avg_val_loss": loss}, f, indent=4)

        return {"loss": loss, "status": STATUS_OK}

    def execute_search(self) -> Dict[str, Any]:
        """
        Executes the hyperparameter search using the defined objective function and search space.

        Returns:
            Dict[str, Any]: Dictionary of best parameters found.
        """
        best_params = fmin(
            fn=self.objective,
            space=self.space,
            algo=tpe.suggest,
            max_evals=self.max_evals,
            trials=self.trials,
        )
        best_params = {k: convert_numpy(v) for k, v in best_params.items()}

        best_params_path = "../../data/cma/rf/model/best_hyperparameters.json"
        with open(best_params_path, "w") as f:
            json.dump(best_params, f, indent=4)

        logger.success(
            f"Best hyperparameters: {best_params} saved to: {best_params_path}"
        )
        return best_params


if __name__ == "__main__":
    hypertuner = HyperparameterTuningWorkflow(max_evals=100)
    best_params = hypertuner.execute_search()
