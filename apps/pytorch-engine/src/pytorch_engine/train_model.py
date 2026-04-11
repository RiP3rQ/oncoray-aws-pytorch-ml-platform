"""
Trains a PyTorch image classification model using device-agnostic code.
"""

import torch
from torchvision import transforms

# TODO: model_builder module with TinyVGG class not yet implemented
# from . import model_builder

# Setup hyperparameters
NUM_EPOCHS = 5
BATCH_SIZE = 32
HIDDEN_UNITS = 10
LEARNING_RATE = 0.001

# Setup directories
train_dir = "data/pizza_steak_sushi/train"
test_dir = "data/pizza_steak_sushi/test"

# Setup target device
device = "cuda" if torch.cuda.is_available() else "cpu"

# Create transforms
data_transform = transforms.Compose(
    [transforms.Resize((64, 64)), transforms.ToTensor()]
)

# # Create DataLoaders with help from data_setup.py
# train_dataloader, test_dataloader, class_names = data_setup.create_dataloaders(
#     train_dir=train_dir,
#     test_dir=test_dir,
#     transform=data_transform,
#     batch_size=BATCH_SIZE,
# )
#
# # TODO: Uncomment when model_builder module with TinyVGG class is implemented
# # model = model_builder.TinyVGG(
# #     input_shape=3, hidden_units=HIDDEN_UNITS, output_shape=len(class_names)
# # ).to(device)
#
# # Set loss and optimizer
# loss_fn = torch.nn.CrossEntropyLoss()
# optimizer = torch.optim.Adam(model.parameters(), lr=LEARNING_RATE)
#
# # Start training with help from training_loop.py
# training_loop.train_model(
#     model=model,
#     train_dataloader=train_dataloader,
#     test_dataloader=test_dataloader,
#     loss_fn=loss_fn,
#     optimizer=optimizer,
#     epochs=NUM_EPOCHS,
#     device=device,
# )
#
# # Save the model with help from save_model.py
# save_model.save_model(
#     model=model,
#     model_name="05_going_modular_script_mode_tinyvgg_model.pth",
#     target_dir="models",
# )
