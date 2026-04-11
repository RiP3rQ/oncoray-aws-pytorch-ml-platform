# EffNetB2 Training Pipeline — Implementation Plan

> Generated from grill-me session. All decisions captured below.

---

## 1. Context

Refactor `src/effnet.ipynb` notebook into a fully functional pipeline that builds a pretrained EffNetB2 model and trains
it on the HAM10000 skin lesion dataset. All reusable logic must be extracted into helper modules under
`src/pytorch_engine/`.

### Notebook Current State

- Section 1 (Data Setup): Working — imports, variables, device, glob/CSV, transforms, dataloaders
- Section 2 (Model): Commented out — model creation, summary, loss/optimizer, training loop, saving, plotting
- Key gap: No actual EffNetB2 model creation or training ever runs

### Dataset Reality

- Images are **flat** in `data/training_data/` and `data/testing_data/` (no class subdirs)
- Labels come from a **CSV metadata file** (`HAM10000_metadata.csv`) mapping `image_id` → `dx` (lesion type)
- ~450 training images, ~50 testing images
- **No pre-existing train/test split** — need to create one from the CSV
- 7 lesion classes (auto-detected from CSV)

---

## 2. Decisions Log

| #   | Question               | Decision                                                                            |
|-----|------------------------|-------------------------------------------------------------------------------------|
| Q1  | Data layout            | Flat images + CSV metadata (`data/` folder)                                         |
| Q2  | Labels source          | CSV metadata (HAM10000_metadata.csv)                                                |
| Q3  | Dataset class approach | **Generic `CSVDataset`** (not HAM10000-specific)                                    |
| Q4  | Transform strategy     | **Custom augmentation for train** + pretrained EffNetB2 default transforms for test |
| Q5  | Image size             | **224×224**                                                                         |
| Q6  | Output artifact        | **Notebook remains the main runner** — helpers go into `pytorch_engine/`            |
| Q7  | Epochs / LR            | **20 epochs, lr=1e-3**                                                              |
| Q8  | Model save path        | `save_model()` default: `packages/pytorch-saved-models/`                            |
| Q9  | Num classes            | **Auto-detect from CSV**                                                            |
| Q10 | Split strategy         | **sklearn train_test_split** (random, not stratified)                               |
| Q11 | Split ratio            | **80/20**                                                                           |

---

## 3. Files to Create/Modify

### 3.1 NEW — `src/pytorch_engine/csv_dataset.py`

Generic CSV-backed image dataset class.

```python
class CSVDataset(torch.utils.data.Dataset):
    """Image dataset backed by a CSV metadata file.

    Reads images from a flat directory, looks up labels from a CSV.
    Configurable column names for image_id and label.
    """
    def __init__(
        self,
        image_dir: str | Path,
        csv_path: str | Path,
        image_id_col: str = "image_id",
        label_col: str = "dx",
        file_extension: str = ".jpg",
        transform: transforms.Compose | None = None,
    ): ...

    def __len__(self) -> int: ...
    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]: ...

    # Properties
    class_names: list[str]      # sorted unique labels
    class_to_idx: dict[str, int]  # label → index mapping


def create_csv_dataloader(
    image_dir: str | Path,
    csv_path: str | Path,
    transform: transforms.Compose,
    batch_size: int = 32,
    shuffle: bool = False,
    num_workers: int = os.cpu_count() or 1,
    image_id_col: str = "image_id",
    label_col: str = "dx",
    file_extension: str = ".jpg",
) -> DataLoaderResult:
    """Create a DataLoader from a flat image directory + CSV metadata.

    Returns DataLoaderResult with dataloader + class_names (same shape as create_dataloader).
    """
```

**Key behaviors:**

- Constructs image paths as `image_dir / {image_id}{file_extension}`
- Builds `class_to_idx` mapping from sorted unique labels in CSV
- Returns `(transformed_image, label_index)` tuples
- `DataLoaderResult` type reused from `data_setup.py` for API consistency

### 3.2 NEW — `src/pytorch_engine/data_split.py`

CSV data splitting utility.

```python
def split_csv_metadata(
    csv_path: str | Path,
    test_size: float = 0.2,
    random_state: int = 42,
    image_dir: str | Path | None = None,
    image_id_col: str = "image_id",
    label_col: str = "dx",
    file_extension: str = ".jpg",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split CSV metadata into train/test DataFrames.

    - Validates that all referenced image files exist in image_dir.
    - Uses sklearn.model_selection.train_test_split.
    - Returns (train_df, test_df) with all original CSV columns preserved.
    """
```

**Key behaviors:**

- Reads CSV, filters rows where image file exists in `image_dir`
- `train_test_split(df, test_size=test_size, random_state=random_state)`
- Returns two DataFrames ready for `CSVDataset`

### 3.3 MODIFY — `src/pytorch_engine/transforms.py`

Add augmentation transform builder:

```python
def get_train_transform(
    image_size: tuple[int, int] = (224, 224),
    normalize_mean: list[float] | None = None,
    normalize_std: list[float] | None = None,
) -> transforms.Compose:
    """Build training transform pipeline with data augmentation.

    When normalize_mean/std are None, falls back to ImageNet defaults.
    """
```

**Pipeline:**

1. `Resize(image_size)`
2. `RandomHorizontalFlip()`
3. `RandomVerticalFlip()`
4. `RandomRotation(20)`
5. `ColorJitter(brightness=0.1, contrast=0.1, hue=0.1)`
6. `ToTensor()`
7. `Normalize(mean=normalize_mean or _IMAGENET_MEAN, std=normalize_std or _IMAGENET_STD)`

### 3.4 MODIFY — `src/pytorch_engine/__init__.py`

Add exports:

```python
from pytorch_engine.csv_dataset import CSVDataset, create_csv_dataloader
from pytorch_engine.data_split import split_csv_metadata
from pytorch_engine.transforms import get_train_transform
```

Add to `__all__`: `CSVDataset`, `create_csv_dataloader`, `split_csv_metadata`, `get_train_transform`

### 3.5 MODIFY — `src/effnet.ipynb`

Complete refactor. Notebook flow:

#### Cell 1 — Imports

```python
import os
from pathlib import Path

import torch
import pandas as pd

from pytorch_engine import (
    create_csv_dataloader,
    get_current_device,
    set_seeds,
    save_model,
)
from pytorch_engine.data_split import split_csv_metadata
from pytorch_engine.models import create_effnetb2_model
from pytorch_engine.training_loop import train_model
from pytorch_engine.transforms import get_train_transform
from pytorch_engine.utils import compute_img_mean_std
from pytorch_engine.visualization import plot_loss_curves
```

#### Cell 2 — Config

```python
# Hyperparameters
IMG_SIZE = 224
BATCH_SIZE = 32
LEARNING_RATE = 1e-3
NUM_EPOCHS = 20
SEED = 42

# Paths
DATA_DIR = Path("../data")
CSV_PATH = DATA_DIR / "HAM10000_metadata.csv"
IMAGE_DIR = DATA_DIR / "images"  # flat image directory
FILE_EXTENSION = ".jpg"

# Device
device = get_current_device()
set_seeds(SEED)
```

#### Cell 3 — Data split

```python
# Split CSV metadata into train/test (80/20)
train_df, test_df = split_csv_metadata(
    csv_path=CSV_PATH,
    test_size=0.2,
    random_state=SEED,
    image_dir=IMAGE_DIR,
    file_extension=FILE_EXTENSION,
)
print(f"Train samples: {len(train_df)}, Test samples: {len(test_df)}")
print(f"Classes: {sorted(train_df['dx'].unique())}")
```

#### Cell 4 — Compute normalization stats

```python
# Compute dataset-specific mean/std for normalization
from glob import glob

all_image_paths = glob(str(IMAGE_DIR / f"*{FILE_EXTENSION}"))
norm_stats = compute_img_mean_std(all_image_paths)
print(f"Mean (RGB): {norm_stats.mean}")
print(f"Std (RGB): {norm_stats.std}")
```

#### Cell 5 — Build transforms

```python
# Custom augmentation for training, pretrained defaults for testing
train_transform = get_train_transform(
    image_size=(IMG_SIZE, IMG_SIZE),
    normalize_mean=norm_stats.mean,
    normalize_std=norm_stats.std,
)

# For test: use EffNetB2's default transforms (provided by create_effnetb2_model)
```

#### Cell 6 — Create dataloaders

```python
# Training dataloader
train_result = create_csv_dataloader(
    image_dir=IMAGE_DIR,
    csv_path=CSV_PATH,
    transform=train_transform,
    batch_size=BATCH_SIZE,
    shuffle=True,
    image_id_col="image_id",
    label_col="dx",
    file_extension=FILE_EXTENSION,
)
train_dataloader = train_result["dataloader"]
class_names = train_result["class_names"]
num_classes = len(class_names)

# Testing dataloader — created after model (for pretrained transforms)
```

**Note:** Test dataloader needs the model's pretrained transforms, so we create it after model creation.

#### Cell 7 — Build model

```python
# Create EffNetB2 model with pretrained weights
effnetb2_result = create_effnetb2_model(
    num_classes=num_classes,
    seed=SEED,
)
model = effnetb2_result.model
effnetb2_transforms = effnetb2_result.transforms

# Create test dataloader using pretrained transforms
test_result = create_csv_dataloader(
    image_dir=IMAGE_DIR,
    csv_path=CSV_PATH,
    transform=effnetb2_transforms,
    batch_size=BATCH_SIZE,
    shuffle=False,
    image_id_col="image_id",
    label_col="dx",
    file_extension=FILE_EXTENSION,
)
test_dataloader = test_result["dataloader"]
```

#### Cell 8 — Print model summary (optional)

```python
from torchinfo import summary
summary(model, input_size=(1, 3, IMG_SIZE, IMG_SIZE),
         col_names=["input_size", "output_size", "num_params", "trainable"],
         col_width=20, row_settings=["var_names"])
```

#### Cell 9 — Loss & optimizer

```python
loss_fn = torch.nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
```

#### Cell 10 — Train

```python
results = train_model(
    model=model,
    train_dataloader=train_dataloader,
    test_dataloader=test_dataloader,
    optimizer=optimizer,
    loss_fn=loss_fn,
    epochs=NUM_EPOCHS,
    device=device,
)
```

#### Cell 11 — Plot results

```python
fig = plot_loss_curves(results)
fig.show()
```

#### Cell 12 — Save model

```python
saved_path = save_model(
    model=model,
    model_name="effnetb2_ham10000.pth",
)
print(f"Model saved to: {saved_path}")
```

---

## 4. Design Decisions & Rationale

### Why Generic CSVDataset (not HAM10000-specific)?

- Reusable for any CSV-backed image dataset
- HAM10000-specific logic (column names, file extensions) is parameterized
- Same pattern works for other medical imaging datasets

### Why Custom Train + Pretrained Test Transforms?

- **Train**: Augmentation (flips, rotation, color jitter) improves generalization on small datasets. Dataset-computed
  mean/std better represents the data distribution than ImageNet defaults.
- **Test**: Pretrained transforms are standardized and guaranteed compatible with the backbone weights. No augmentation
  on test data.

### Why 224×224 Instead of 288×288?

- User choice — smaller input means faster training iterations
- EffNetB2 handles 224×224 fine (it's a resize layer, not architecture-dependent)

### Why Random (Not Stratified) Split?

- User chose random split with sklearn
- HAM10000 is imbalanced — consider switching to stratified if class distribution matters
- Easy to change: `split_csv_metadata` can add a `stratify` parameter later

### Why Notebook Remains the Runner?

- Interactive exploration — can inspect intermediate DataFrames, plots, outputs
- Jupyter pattern fits ML experimentation workflow
- Helpers in `pytorch_engine/` are reusable for future scripts

---

## 5. Dependencies

Current `pyproject.toml` should already have:

- `torch`, `torchvision`
- `pandas`
- `opencv-python` (for `compute_img_mean_std`)

**New dependency needed:**

- `scikit-learn` — for `train_test_split` in `data_split.py`

**Optional dependency:**

- `torchinfo` — for model summary in notebook (already used in commented cells)

---

## 6. File Impact Summary

| File                            | Action     | Purpose                                               |
|---------------------------------|------------|-------------------------------------------------------|
| `pytorch_engine/csv_dataset.py` | **CREATE** | Generic CSV-backed image dataset + dataloader factory |
| `pytorch_engine/data_split.py`  | **CREATE** | Train/test split from CSV metadata                    |
| `pytorch_engine/transforms.py`  | **MODIFY** | Add `get_train_transform()` with augmentation         |
| `pytorch_engine/__init__.py`    | **MODIFY** | Export new public API                                 |
| `effnet.ipynb`                  | **MODIFY** | Full refactor — working pipeline using all helpers    |
