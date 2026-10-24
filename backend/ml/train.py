import argparse
import hashlib
import json
import random
from pathlib import Path

import timm
import torch
from PIL import Image
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from torch import nn
from torch.utils.data import DataLoader, Dataset
from timm.data import create_transform, resolve_model_data_config
from torchvision.datasets import ImageFolder

ARCHITECTURE = "mobilenetv3_small_100"
IMAGE_SIZE = 224
DEFAULT_CLASSES = (
    "Tomato_healthy",
    "Tomato_Early_blight",
    "Tomato_Late_blight",
    "Tomato_Bacterial_spot",
)
TRAIN_AUTO_AUGMENT = "rand-m9-mstd0.5"


class CropImageDataset(Dataset):
    def __init__(self, samples, transform):
        self.samples = samples
        self.transform = transform

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, index):
        image_path, label = self.samples[index]
        with Image.open(image_path) as source:
            image = source.convert("RGB")
        return self.transform(image), label


def collect_class_samples(dataset_root: Path, class_names: tuple[str, ...], max_per_class: int, seed: int):
    source = ImageFolder(dataset_root)
    unknown = sorted(set(class_names) - set(source.classes))
    if unknown:
        raise ValueError(f"Dataset is missing class folders: {', '.join(unknown)}")

    source_indices = {name: source.class_to_idx[name] for name in class_names}
    rng = random.Random(seed)
    selected = {}
    hashes = set()
    for label, class_name in enumerate(class_names):
        candidates = [
            Path(path)
            for path, original_label in source.samples
            if original_label == source_indices[class_name]
        ]
        rng.shuffle(candidates)
        class_samples = []
        for path in candidates:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if digest in hashes:
                continue
            hashes.add(digest)
            class_samples.append((str(path), label))
            if len(class_samples) == max_per_class:
                break
        if len(class_samples) < 3:
            raise ValueError(f"Class '{class_name}' needs at least 3 unique images.")
        selected[class_name] = class_samples
    return selected


def split_samples(class_samples, seed: int):
    rng = random.Random(seed)
    splits = {"train": [], "val": [], "test": []}
    for class_name, samples in class_samples.items():
        samples = list(samples)
        rng.shuffle(samples)
        test_count = max(1, round(len(samples) * 0.15))
        val_count = max(1, round(len(samples) * 0.15))
        if test_count + val_count >= len(samples):
            raise ValueError(f"Class '{class_name}' has too few images for train/val/test splits.")
        splits["test"].extend(samples[:test_count])
        splits["val"].extend(samples[test_count:test_count + val_count])
        splits["train"].extend(samples[test_count + val_count:])
    for split_samples_list in splits.values():
        rng.shuffle(split_samples_list)
    return splits


def evaluate(model, loader, device, class_names):
    model.eval()
    predictions, labels = [], []
    with torch.inference_mode():
        for images, targets in loader:
            logits = model(images.to(device))
            predictions.extend(logits.argmax(dim=1).cpu().tolist())
            labels.extend(targets.tolist())
    return {
        "accuracy": accuracy_score(labels, predictions),
        "sample_count": len(labels),
        "classification_report": classification_report(
            labels,
            predictions,
            labels=list(range(len(class_names))),
            target_names=class_names,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(
            labels, predictions, labels=list(range(len(class_names)))
        ).tolist(),
    }


def train(
    dataset_root: Path,
    checkpoint_path: Path,
    epochs: int,
    batch_size: int,
    max_per_class: int,
    class_names: tuple[str, ...] = DEFAULT_CLASSES,
    seed: int = 17,
):
    torch.manual_seed(seed)
    class_samples = collect_class_samples(dataset_root, class_names, max_per_class, seed)
    splits = split_samples(class_samples, seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = timm.create_model(ARCHITECTURE, pretrained=True, num_classes=len(class_names))
    data_config = resolve_model_data_config(model)
    data_config["input_size"] = (3, IMAGE_SIZE, IMAGE_SIZE)
    transforms = {
        "train": create_transform(
            **data_config, is_training=True, auto_augment=TRAIN_AUTO_AUGMENT
        ),
        "val": create_transform(**data_config, is_training=False),
        "test": create_transform(**data_config, is_training=False),
    }
    datasets = {
        split: CropImageDataset(samples, transforms[split])
        for split, samples in splits.items()
    }
    loaders = {
        split: DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=split == "train",
            num_workers=0,
        )
        for split, dataset in datasets.items()
    }

    for parameter in model.parameters():
        parameter.requires_grad = False
    classifier = model.get_classifier()
    for parameter in classifier.parameters():
        parameter.requires_grad = True

    model.to(device)
    optimizer = torch.optim.AdamW(classifier.parameters(), lr=1e-3, weight_decay=1e-4)
    criterion = nn.CrossEntropyLoss()
    best_val_accuracy = -1.0
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(epochs):
        model.train()
        train_correct = train_count = 0
        for images, labels in loaders["train"]:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = criterion(logits, labels)
            loss.backward()
            optimizer.step()
            train_correct += (logits.argmax(dim=1) == labels).sum().item()
            train_count += labels.size(0)

        validation = evaluate(model, loaders["val"], device, class_names)
        val_accuracy = validation["accuracy"]
        print(
            f"epoch={epoch + 1}/{epochs} "
            f"train_accuracy={train_correct / max(train_count, 1):.4f} "
            f"val_accuracy={val_accuracy:.4f} "
            f"val_samples={validation['sample_count']}",
            flush=True,
        )
        if val_accuracy > best_val_accuracy:
            best_val_accuracy = val_accuracy
            torch.save(
                {
                    "architecture": ARCHITECTURE,
                    "state_dict": model.state_dict(),
                    "classes": list(class_names),
                    "data_config": data_config,
                    "training_config": {
                        "seed": seed,
                        "epochs": epochs,
                        "max_per_class": max_per_class,
                        "image_size": IMAGE_SIZE,
                        "classifier_only": True,
                    },
                },
                checkpoint_path,
            )

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model.load_state_dict(checkpoint["state_dict"])
    test_metrics = evaluate(model, loaders["test"], device, class_names)
    test_metrics["classes"] = list(class_names)
    test_metrics["training_config"] = checkpoint["training_config"]
    checkpoint["held_out_test_accuracy"] = test_metrics["accuracy"]
    checkpoint["held_out_test_samples"] = test_metrics["sample_count"]
    torch.save(checkpoint, checkpoint_path)
    report_path = checkpoint_path.with_suffix(".test-metrics.json")
    report_path.write_text(json.dumps(test_metrics, indent=2), encoding="utf-8")
    print(
        f"HELD_OUT_TEST_ACCURACY={test_metrics['accuracy']:.4%} "
        f"TEST_SAMPLES={test_metrics['sample_count']}",
        flush=True,
    )
    print(f"Metrics report: {report_path}", flush=True)
    print(json.dumps(test_metrics["classification_report"], indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Train and evaluate a balanced tomato crop classifier."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("dataset/PlantVillage/PlantVillage/PlantVillage"),
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=Path("backend/models/efficientnetv2_s.pth"),
    )
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-per-class", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--classes", nargs="+", default=list(DEFAULT_CLASSES))
    args = parser.parse_args()
    if args.epochs < 1 or args.batch_size < 1 or args.max_per_class < 3:
        parser.error("--epochs, --batch-size, and --max-per-class must be positive (at least 3 images per class).")
    train(
        args.dataset,
        args.checkpoint,
        args.epochs,
        args.batch_size,
        args.max_per_class,
        tuple(args.classes),
        args.seed,
    )


if __name__ == "__main__":
    main()
