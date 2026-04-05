from __future__ import annotations

import argparse

import torch


def train(epochs: int, learning_rate: float) -> torch.nn.Module:
    torch.manual_seed(7)

    inputs = torch.linspace(-1, 1, 100).unsqueeze(1)
    targets = 2 * inputs + 0.3

    model = torch.nn.Sequential(torch.nn.Linear(1, 1))
    loss_fn = torch.nn.MSELoss()
    optimizer = torch.optim.SGD(model.parameters(), lr=learning_rate)

    for epoch in range(epochs):
        predictions = model(inputs)
        loss = loss_fn(predictions, targets)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if epoch == 0 or (epoch + 1) % 50 == 0 or epoch == epochs - 1:
            print(f"epoch={epoch + 1:03d} loss={loss.item():.6f}")

    return model


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train a simple linear PyTorch model on synthetic data."
    )
    parser.add_argument("--epochs", type=int, default=200)
    parser.add_argument("--learning-rate", type=float, default=0.1)
    args = parser.parse_args()

    model = train(args.epochs, args.learning_rate)
    layer = model[0]
    weight = layer.weight.item()
    bias = layer.bias.item()

    print(f"trained weight={weight:.4f} bias={bias:.4f}")


if __name__ == "__main__":
    main()
