from pydantic import BaseModel, Field
from typing import Optional

class TrainConfig(BaseModel):
    shipowner: str = "cma"
    num_checkpoints: int = 3
    with_augmentation: bool = False
    k_fold: int = 5
    num_epochs: int = 10
    resume_run: Optional[str] = None
    learning_rate: float = 0.001  # 0.0001
    batch_size: int = 16
    dropout_rate: Optional[float] = None  # 0.5
    weight_decay: float = 0  # 1e-4
    drop_categories: Optional[int] = None
