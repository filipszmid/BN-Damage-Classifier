import datetime
import json
import os
from pathlib import Path

import pandas as pd
import torch
from loguru import logger
from random_word import RandomWords
from sklearn.model_selection import StratifiedKFold
from sklearn.model_selection import train_test_split
from torch import nn, optim
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter
from torchvision import transforms

from src.classifier.config import TrainConfig
from src.classifier.data_agumentation import DataAugmentationWorkflow
from src.classifier.dataset import ContainerDamageDataset
from src.classifier.encoder import DynamicEncoder
from src.classifier.model import ResNetClassifier
from src.classifier.utils import merge_and_save_csv, aggregate_category_counts
from src.config import get_project_root


class TrainWorkflow:
    def __init__(self, config: TrainConfig):
        """
        Initialize the TrainWorkflow class with base configurations.
        Args:
        config (TrainConfig): Training config variable.
        """

        self.config = config
        self.k_fold = config.k_fold
        self.data_path = os.path.join(
            get_project_root(),
            "data",
            config.shipowner,
            "row_map_dataset.csv",
        )
        self.num_checkpoints = config.num_checkpoints
        self.with_augmentation = config.with_augmentation
        self.learning_rate = config.learning_rate
        self.batch_size = config.batch_size
        self.dropout_rate = config.dropout_rate
        self.weight_decay = config.weight_decay
        self.metadata_file = os.path.join(
            get_project_root(),
            "data",
            config.shipowner,
            "metadata_reports_1.json",
        )
        self.num_epochs = config.num_epochs
        self.drop_categories = config.drop_categories
        self.run_name = (
            config.resume_run if config.resume_run else self.generate_new_run_name()
        )
        self.base_path = os.path.join(
            get_project_root(),
            "data",
            config.shipowner,
            "model",
            self.run_name,
        )
        os.makedirs(self.base_path, exist_ok=True)
        # TODO: Edge case: What if resume run but with different drop categories?
        self.encoder = DynamicEncoder(self.data_path, self.base_path, config.drop_categories)
        self.train_loader, self.val_loader = None, None
        self.model, self.criterion, self.optimizer = self.setup_model()

        # It assumes if it continues run any checkpoint need to exist

        self.checkpoint_path = self.find_latest_checkpoint(self.base_path)

        if self.checkpoint_path:
            checkpoint_state = self.load_checkpoint(self.checkpoint_path)
            self.run_name = checkpoint_state["run_name"]
            logger.info(
                f"Resuming training from checkpoint: {self.checkpoint_path}, run name: {self.run_name}"
            )
        else:
            logger.info(f"Starting new training run: {self.run_name}")

        self.checkpoint_dir = os.path.join(self.base_path, "checkpoints")
        os.makedirs(self.checkpoint_dir, exist_ok=True)

        logger.add(os.path.join(self.base_path, "training.log"))

        self.writer = SummaryWriter(
            comment=f"run_{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}",
            log_dir=os.path.join(self.base_path, "logs"),
        )
        self.encoder.save_mappings()

        self.writer.add_hparams(
            {
                "learning_rate": self.learning_rate,
                "batch_size": self.batch_size,
                "k_fold": self.k_fold,
                "dropout_rate": self.dropout_rate,
                "weight_decay": self.weight_decay,
                "num_epochs": 0 if not config.resume_run else checkpoint_state["epoch"],
                "with_augmentation": self.with_augmentation,
                "path_to_checkpoint": self.checkpoint_path,
                "drop_categories": self.drop_categories,
            },
            {
                "hparam/train_loss": -1
                if not config.resume_run
                else checkpoint_state["train_loss"],
                "hparam/val_loss": -1
                if not config.resume_run
                else checkpoint_state["loss"],
            },
        )

        with open(os.path.join(self.base_path, "training_config.json"), "w") as f:
            json.dump({**config.dict()}, f, indent=4)

    def find_latest_k_fold_checkpoint(self):
        latest_epoch = -1
        latest_fold = -1
        latest_checkpoint = None

        for fold in range(1, self.config.k_fold + 1):
            fold_path = os.path.join(self.base_path, f"fold_{fold}", "checkpoints")
            checkpoints = list(Path(fold_path).glob("*.pth"))
            if checkpoints:
                fold_latest_checkpoint = max(checkpoints, key=os.path.getctime)
                epoch = int(fold_latest_checkpoint.stem.split("_")[-1])
                if epoch > latest_epoch:
                    latest_epoch = epoch
                    latest_fold = fold
                    latest_checkpoint = str(fold_latest_checkpoint)

        return latest_fold, latest_epoch, latest_checkpoint

    def prepare_k_fold_data(self, k_fold):
        """
        Prepare training and validation datasets for K-Fold cross-validation and save to CSV files.
        Args:
            k_fold (int): The number of folds to split the data into.
        """
        if self.checkpoint_path is None:  # Prepare new data for new run
            data = pd.read_csv(self.data_path)
            data = data.dropna(subset=["metadata"])
            data["metadata_json"] = data["metadata"].apply(json.loads)
            data["location"] = data["metadata_json"].apply(
                lambda x: x.get("location", "")
            )
            data["component"] = data["metadata_json"].apply(
                lambda x: x.get("component", "")
            )
            data["repair_type"] = data["metadata_json"].apply(
                lambda x: x.get("repair_type", "")
            )
            data["damage"] = data["metadata_json"].apply(lambda x: x.get("damage", ""))

            # Create a stratification column if needed
            if self.drop_categories:
                data = self._filter_categories(data)

            # Create a single stratification key
            data["stratify_key"] = data.apply(
                lambda x: f"{x['location']}_{x['component']}_{x['repair_type']}_{x['damage']}",
                axis=1,
            )

            skf = StratifiedKFold(n_splits=k_fold, shuffle=True, random_state=42)
            for fold, (train_idx, val_idx) in enumerate(
                skf.split(data, data["stratify_key"])
            ):
                fold_base_path = os.path.join(self.base_path, f"fold_{fold + 1}")
                os.makedirs(fold_base_path, exist_ok=True)
                sf_data_path = os.path.join(fold_base_path, "stratified_data.csv")
                data.to_csv(sf_data_path)
                aggregate_category_counts(
                    sf_data_path, os.path.join(fold_base_path, "stratified_category_count.csv")
                )
                train_data, val_data = data.iloc[train_idx], data.iloc[val_idx]
                train_data_path = os.path.join(fold_base_path, "train_data.csv")
                val_data_path = os.path.join(fold_base_path, "val_data.csv")
                train_data.to_csv(train_data_path, index=False)
                val_data.to_csv(val_data_path, index=False)
                logger.info(f"Data for fold {fold + 1} saved in {fold_base_path}")

    def _filter_categories(self, data):
        """
        Filters categories based on the 'drop_categories' threshold and saves the filtered dataset.
        """
        category_counts = aggregate_category_counts(
            self.data_path, os.path.join(self.base_path, "category_counts.csv")# TODO: overrides existing file
        )
        counts_filtered = category_counts[
            category_counts["counts"] >= self.drop_categories
        ]
        filter_criteria = counts_filtered[
            ["location", "component", "repair_type", "damage"]
        ]
        filtered_data = pd.merge(
            data,
            filter_criteria,
            on=["location", "component", "repair_type", "damage"],
            how="inner",
        )
        logger.info("Filtered categories based on the specified threshold.")
        return filtered_data

    def train_k_fold(self):
        """
        Train the model using K-Fold cross-validation.
        """
        for fold in range(1, self.config.k_fold + 1):
            self.current_fold = fold  # Update current fold

            logger.info(f"Training fold {fold}/{self.config.k_fold}")

            # Load the training and validation data for the current fold
            train_data_path = os.path.join(
                self.base_path, f"fold_{fold}", "train_data.csv"
            )
            val_data_path = os.path.join(self.base_path, f"fold_{fold}", "val_data.csv")
            train_data = pd.read_csv(train_data_path)
            val_data = pd.read_csv(val_data_path)

            # Prepare data loaders
            train_loader, val_loader = self._prepare_dataloaders(train_data, val_data)

            # Perform training for the current fold
            self.train_fold(train_loader, val_loader)

    def train_fold(self, train_loader, val_loader):
        """
        Train the model for a single fold and validate after each epoch, using multiple output handling.
        """
        checkpoint_path = None
        for epoch in range(self.num_epochs):
            # Training Phase
            self.model.train()
            total_train_loss = 0
            for images, labels in train_loader:
                self.optimizer.zero_grad()
                outputs = self.model(images)

                # Calculate loss as the sum of losses of all model outputs
                losses = [
                    self.criterion(output, labels[idx].squeeze())
                    for idx, output in enumerate(outputs)
                ]
                total_loss = sum(losses)

                total_loss.backward()
                self.optimizer.step()
                total_train_loss += total_loss.item()

                # Logging training progress
                if (
                    images.shape[0] - 1
                ) % 5 == 0:  # Adjust the logging frequency as needed
                    logger.info(
                        f"Epoch [{epoch + 1}/{self.num_epochs}], Batch Loss: {total_loss.item():.4f}"
                    )

            average_train_loss = total_train_loss / len(train_loader.dataset)
            logger.info(
                f"End of Epoch {epoch + 1}, Training Loss: {average_train_loss:.4f}"
            )
            self.writer.add_scalar(f"Fold_{self.current_fold}/Average Epoch Loss", average_train_loss, epoch)
            self.writer.add_scalar(f"Fold_{self.current_fold}/Total Epoch Loss", total_train_loss, epoch)
            # Validation Phase
            self.model.eval()
            total_val_loss = 0
            with torch.no_grad():
                for images, labels in val_loader:
                    outputs = self.model(images)
                    losses = [
                        self.criterion(output, labels[idx].squeeze())
                        for idx, output in enumerate(outputs)
                    ]
                    batch_loss = sum(losses)
                    total_val_loss += batch_loss.item()

            average_val_loss = total_val_loss / len(val_loader.dataset)
            logger.info(f"Epoch {epoch + 1}, Validation Loss: {average_val_loss:.4f}")
            self.writer.add_scalar(f"Fold_{self.current_fold}/Average Validation Loss", average_val_loss, epoch)
            self.writer.add_scalar(f"Fold_{self.current_fold}/Total Validation Loss", total_val_loss, epoch)
            # Save checkpoints at the end of each epoch if necessary
            if (epoch + 1) % self.num_checkpoints == 0 or epoch + 1 == self.num_epochs:
                checkpoint_path = os.path.join(
                    self.checkpoint_dir,
                    f"fold_{self.current_fold}_epoch_{epoch + 1}.pth",
                )
                torch.save(
                    {
                        "epoch": epoch + 1,
                        "model_state_dict": self.model.state_dict(),
                        "optimizer_state_dict": self.optimizer.state_dict(),
                        "train_loss": average_train_loss,
                        "val_loss": average_val_loss,
                        "run_name": self.run_name,
                    },
                    checkpoint_path,
                )
                logger.info(
                    f"Checkpoint for fold {self.current_fold}, epoch {epoch + 1} saved at {checkpoint_path}"
                )
            self.writer.add_hparams(
                {
                    "learning_rate": self.learning_rate,
                    "batch_size": self.batch_size,
                    "current_fold": self.current_fold,
                    "dropout_rate": self.dropout_rate,
                    "weight_decay": self.weight_decay,
                    "num_epochs": epoch + 1,
                    "with_augmentation": self.with_augmentation,
                    "path_to_checkpoint": checkpoint_path if checkpoint_path else None,
                    "drop_categories": self.drop_categories,
                },
                {
                    "hparam/epoch_loss": average_train_loss,
                    "hparam/val_loss": average_val_loss,
                },
            )

    def prepare_data(self):
        """
        Prepare training and validation datasets and data loaders.
        Returns:
        tuple: Tuple containing DataLoader for training and validation datasets.
        """
        if self.config.k_fold > 1:
            # If K-Fold is specified and greater than 1, prepare data using K-Fold method
            self.prepare_k_fold_data(self.config.k_fold)
            return None
        else:
            if self.checkpoint_path is None:  # render new data for new run
                data = pd.read_csv(self.data_path)
                data = data.dropna(subset=["metadata"])

                if self.drop_categories:
                    data = self._drop_train_data(data)

                train_data, val_data = train_test_split(
                    data, test_size=0.2, random_state=42
                )
                train_data.to_csv(
                    os.path.join(self.base_path, "train_data.csv"), index=False
                )

                if self.with_augmentation:
                    train_data = self._run_augmentation()

                val_data.to_csv(
                    os.path.join(self.base_path, "val_data.csv"), index=False
                )

            else:  # just load data from run checkpoint
                if os.path.exists(os.path.join(self.base_path, "augmentation")):
                    train_data = pd.read_csv(
                        os.path.join(self.base_path, "train_data_concat.csv")
                    )
                    logger.info("Got train data with augmentation.")
                else:
                    train_data = pd.read_csv(
                        os.path.join(self.base_path, "train_data.csv")
                    )
                    logger.info("Got train data without augmentation.")
                val_data = pd.read_csv(os.path.join(self.base_path, "val_data.csv"))
                logger.info("Loaded data generated for previous run.")

            return self._prepare_dataloaders(train_data, val_data)

    def _prepare_dataloaders(self, train_data, val_data):
        transform = transforms.Compose(
            [
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(
                    mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]
                ),
            ]
        )
        train_dataset = ContainerDamageDataset(train_data, self.encoder, transform)
        val_dataset = ContainerDamageDataset(val_data, self.encoder, transform)
        train_loader = DataLoader(
            train_dataset, batch_size=self.batch_size, shuffle=True
        )
        val_loader = DataLoader(val_dataset, batch_size=self.batch_size)
        self.train_loader, self.val_loader = train_loader, val_loader
        return train_loader, val_loader

    def _drop_train_data(self, data):
        category_counts = aggregate_category_counts(
            self.data_path,
            os.path.join(self.base_path, "category_count.csv"),
        )

        logger.info(
            f"Droping categories with less then: {self.drop_categories} pictures."
        )
        data["metadata_json"] = data["metadata"].apply(json.loads)
        data["location"] = data["metadata_json"].apply(lambda x: x.get("location", ""))
        data["component"] = data["metadata_json"].apply(
            lambda x: x.get("component", "")
        )
        data["repair_type"] = data["metadata_json"].apply(
            lambda x: x.get("repair_type", "")
        )
        data["damage"] = data["metadata_json"].apply(lambda x: x.get("damage", ""))

        counts_filtered = category_counts[
            category_counts["counts"] >= self.drop_categories
        ]
        filter_criteria = counts_filtered[
            ["location", "component", "repair_type", "damage"]
        ]

        data = pd.merge(
            data,
            filter_criteria,
            on=["location", "component", "repair_type", "damage"],
            how="inner",
        )

        data.to_csv(
            os.path.join(self.base_path, "row_map_dataset_dropped_categories.csv"),
            index=False,
        )

        logger.info("Current category state after drop:")
        category_counts = aggregate_category_counts(
            os.path.join(self.base_path, "row_map_dataset_dropped_categories.csv"),
            os.path.join(self.base_path, "category_count_after_drop.csv"),
        ) # TODO: doesn't save in k fold after drop
        return data

    def _run_augmentation(self):
        logger.info("Starting augmentation, it can take a while, categories numbers:")
        workflow = DataAugmentationWorkflow(
            input_csv_path=os.path.join(self.base_path, "train_data.csv"),
            output_csv_path=os.path.join(self.base_path, "train_data_augmented.csv"),
            augmented_folder=os.path.join(self.base_path, "augmentation"),
            category_count_path=os.path.join(self.base_path, "category_count.csv"),
        )
        workflow.process_augmentation(num_rows=None)
        merge_and_save_csv(
            os.path.join(self.base_path, "train_data.csv"),
            os.path.join(self.base_path, "train_data_augmented.csv"),
            os.path.join(self.base_path, "train_data_concat.csv"),
        )
        logger.info("Data augmented, categories numbers:")
        category_counts = aggregate_category_counts(
            os.path.join(self.base_path, "train_data_concat.csv"),
            os.path.join(self.base_path, "category_count_concat.csv"),
        )
        train_data = pd.read_csv(os.path.join(self.base_path, "train_data_concat.csv"))
        return train_data

    def calculate_label_maxes(self):
        """
        Calculate the maximum label indices directly from encoder mappings.
        Returns:
        dict: A dictionary of maximum label indices for each category.
        """
        max_values = {
            "location": max(self.encoder.location_map.values(), default=-1),
            "component": max(self.encoder.component_map.values(), default=-1),
            "repair_type": max(self.encoder.repair_type_map.values(), default=-1),
            "damage": max(self.encoder.damage_map.values(), default=-1),
        }
        # Adjust the max indices by 1 to account for zero-based index to one-based count
        max_values = {key: value + 1 for key, value in max_values.items()}
        return max_values

    def setup_model(self):
        """
        Setup the neural network model, loss criterion, and optimizer.
        Returns:
        tuple: Tuple containing the model, criterion, and optimizer.
        """
        model = ResNetClassifier(
            self.calculate_label_maxes(), dropout_rate=self.dropout_rate
        )
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(
            model.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay
        )  # :TODO  different optimizer + normalization of data + low lr
        return model, criterion, optimizer

    def load_checkpoint(self, checkpoint_path):
        """
        Load model, optimizer, epoch state, and run_name from a checkpoint.
        """
        checkpoint = torch.load(checkpoint_path)
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.start_epoch = checkpoint["epoch"]
        self.checkpoint_state = checkpoint
        logger.info(f"Resuming training from epoch {self.start_epoch}")
        return checkpoint

    def generate_new_run_name(self) -> str:
        r = RandomWords()
        fuzzy_word = r.get_random_word()
        run_name = (
            f"run_{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}_{fuzzy_word}"
        )
        return run_name

    def find_latest_checkpoint(self, base_path) -> str | None:
        checkpoint_dir = Path(base_path) / "checkpoints"
        if checkpoint_dir.exists():
            checkpoints = list(checkpoint_dir.glob("*.pth"))
            if checkpoints:
                latest_checkpoint = max(checkpoints, key=os.path.getctime)
                return str(latest_checkpoint)
        return None

    def train_model(self) -> float:
        """
        Train the model using the training and validation data loaders.
        """
        avg_val_loss = None
        start_epoch = getattr(self, "start_epoch", 0)
        checkpoint_path = None
        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)

        for epoch in range(start_epoch, self.num_epochs):
            self.model.train()
            epoch_loss = 0.0
            for i, (images, labels) in enumerate(self.train_loader):
                self.optimizer.zero_grad()

                outputs = self.model(images)
                losses = [
                    self.criterion(output, labels[idx].squeeze())
                    for idx, output in enumerate(outputs)
                ]
                total_loss = sum(losses)

                total_loss.backward()
                self.optimizer.step()
                epoch_loss += total_loss.item()

                if (i + 1) % 10 == 0 or i + 1 == len(self.train_loader):
                    logger.info(
                        f"Epoch [{epoch + 1}/{self.num_epochs}], Step [{i + 1}/{len(self.train_loader)}], Loss: {total_loss.item():.4f}"
                    )
                    self.writer.add_scalar(
                        "Training loss",
                        total_loss.item(),
                        epoch * len(self.train_loader) + i,
                    )

            avg_epoch_loss = epoch_loss / len(self.train_loader.dataset)
            logger.info(
                f"End of Epoch [{epoch + 1}/{self.num_epochs}], Epoch Loss: {avg_epoch_loss:.4f}"
            )
            self.writer.add_scalar("Average Epoch Loss", avg_epoch_loss, epoch)
            self.writer.add_scalar("Total Epoch Loss", epoch_loss, epoch)

            self.model.eval()
            val_loss = 0.0
            with torch.no_grad():
                for images, labels in self.val_loader:
                    outputs = self.model(images)
                    losses = [
                        self.criterion(output, labels[idx].squeeze())
                        for idx, output in enumerate(outputs)
                    ]
                    batch_loss = sum(losses)
                    val_loss += batch_loss.item()

            avg_val_loss = val_loss / len(self.val_loader.dataset)
            logger.info(f"Avg validation Loss: {avg_val_loss:.4f}")
            self.writer.add_scalar("Average Validation Loss", avg_val_loss, epoch)
            self.writer.add_scalar("Total Validation Loss", val_loss, epoch)

            if (epoch + 1) % self.num_checkpoints == 0 or epoch + 1 == self.num_epochs:
                checkpoint_path = os.path.join(
                    self.checkpoint_dir, f"model_epoch_{epoch + 1}.pth"
                )
                torch.save(
                    {
                        "epoch": epoch + 1,
                        "model_state_dict": self.model.state_dict(),
                        "optimizer_state_dict": self.optimizer.state_dict(),
                        "loss": avg_val_loss,
                        "time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "run_name": self.run_name,
                        "train_loss": avg_epoch_loss,
                    },
                    checkpoint_path,
                )
                logger.info(f"Checkpoint saved: {checkpoint_path}")

            # for capturing the state of params and metrics for each epoch
            self.writer.add_hparams(
                {
                    "learning_rate": self.learning_rate,
                    "batch_size": self.batch_size,
                    "k_fold": self.k_fold,
                    "dropout_rate": self.dropout_rate,
                    "weight_decay": self.weight_decay,
                    "num_epochs": epoch + 1,
                    "with_augmentation": self.with_augmentation,
                    "path_to_checkpoint": checkpoint_path if checkpoint_path else None,
                    "drop_categories": self.drop_categories,
                },
                {
                    "hparam/epoch_loss": epoch_loss,
                    "hparam/val_loss": avg_val_loss,
                },
            )
        self.writer.close()
        return avg_val_loss


if __name__ == "__main__":
    # run_name = "run_20240801-122306_unnationally"
    run_name = "run_20240807-152905_paranephritis"
    run_name = "run_20240809-185823_crony"
    run_name = None

    config = TrainConfig(
        shipowner="cma",
        k_fold=5,  # decrease error
        num_checkpoints=3,
        with_augmentation=False,  # augmentation increased the error, extend much epoch length
        num_epochs=30,  # around 30 epochs is the most time enough
        resume_run=run_name,
        learning_rate= 5e-05,  # 10e-6 lowering makes graph smoother
        batch_size=16,
        dropout_rate=0,  # 0.5 can be too aggressive for simple NN
        weight_decay=0.1,  # can be useful but don't change much
        drop_categories=10,  # simplify problem by 10 times
    )
    train_workflow = TrainWorkflow(config)

    if config.k_fold > 1:
        train_workflow.prepare_data()
        train_workflow.train_k_fold()  # Handle training across all K-folds
    else:
        train_workflow.prepare_data()
        train_workflow.train_model()  # Standard training
