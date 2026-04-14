"""pytorch_engine — PyTorch training and inference utilities."""

from pytorch_engine.csv_dataset import CSVDataset, create_csv_dataloader
from pytorch_engine.data_setup import (
    CHEST_XRAY_CLASS_NAMES,
    CHEST_XRAY_SPLITS,
    DataLoaderResult,
    create_dataloader,
    download_and_prepare_kaggle_chest_xray_pneumonia_dataset,
    download_and_prepare_kaggle_ham10000_dataset,
    download_with_curl,
    prepare_kaggle_chest_xray_pneumonia_dataset,
    prepare_kaggle_ham10000_dataset,
)
from pytorch_engine.data_split import split_csv_metadata
from pytorch_engine.evaluation import ClassificationMetrics, evaluate_classification_model
from pytorch_engine.regularization import MixUpBatchTransform, SoftTargetCrossEntropyLoss
from pytorch_engine.save_model import (
    create_milestone_checkpoint_callback,
    save_model,
    upload_model_file_to_huggingface,
)
from pytorch_engine.transforms import get_train_transform
from pytorch_engine.utils import (
    accuracy_fn,
    get_current_device,
    print_train_time,
    resolve_device,
    set_seeds,
)

__all__ = [
    "CSVDataset",
    "CHEST_XRAY_CLASS_NAMES",
    "CHEST_XRAY_SPLITS",
    "ClassificationMetrics",
    "DataLoaderResult",
    "accuracy_fn",
    "create_csv_dataloader",
    "create_dataloader",
    "create_milestone_checkpoint_callback",
    "download_and_prepare_kaggle_chest_xray_pneumonia_dataset",
    "download_and_prepare_kaggle_ham10000_dataset",
    "download_with_curl",
    "evaluate_classification_model",
    "get_current_device",
    "get_train_transform",
    "MixUpBatchTransform",
    "prepare_kaggle_chest_xray_pneumonia_dataset",
    "prepare_kaggle_ham10000_dataset",
    "print_train_time",
    "resolve_device",
    "save_model",
    "set_seeds",
    "split_csv_metadata",
    "SoftTargetCrossEntropyLoss",
    "upload_model_file_to_huggingface",
]
