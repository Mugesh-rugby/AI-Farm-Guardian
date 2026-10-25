import tempfile
import unittest
from pathlib import Path

from PIL import Image
from torch import nn
from timm.data import create_transform

from backend.ml.train import (
    TRAIN_AUTO_AUGMENT,
    collect_class_samples,
    enable_full_model_training,
    split_samples,
)


class ModelDataSplitTests(unittest.TestCase):
    def test_full_finetuning_enables_every_model_parameter(self):
        model = nn.Sequential(nn.Linear(4, 3), nn.Linear(3, 2))
        for parameter in model[0].parameters():
            parameter.requires_grad = False

        trainable_parameters = enable_full_model_training(model)

        self.assertEqual(len(trainable_parameters), len(list(model.parameters())))
        self.assertTrue(all(parameter.requires_grad for parameter in model.parameters()))

    def test_training_augmentation_handles_rgb_images(self):
        transform = create_transform(
            input_size=(3, 224, 224),
            is_training=True,
            auto_augment=TRAIN_AUTO_AUGMENT,
        )
        image = Image.new("RGB", (224, 224), color=(75, 140, 45))

        for _ in range(32):
            self.assertEqual(tuple(transform(image).shape), (3, 224, 224))

    def test_class_selection_is_capped_and_splits_are_disjoint(self):
        class_names = ("tomato_healthy", "tomato_blight")
        with tempfile.TemporaryDirectory() as temporary_directory:
            dataset_root = Path(temporary_directory)
            for class_index, class_name in enumerate(class_names):
                class_directory = dataset_root / class_name
                class_directory.mkdir()
                for image_index in range(12):
                    color = (class_index * 100 + image_index, image_index * 10, 200)
                    Image.new("RGB", (64, 64), color=color).save(class_directory / f"{image_index}.png")

            selected = collect_class_samples(dataset_root, class_names, max_per_class=8, seed=3)
            splits = split_samples(selected, seed=3)

        self.assertEqual([len(selected[name]) for name in class_names], [8, 8])
        paths = {
            split: {path for path, _ in split_samples_list}
            for split, split_samples_list in splits.items()
        }
        self.assertTrue(paths["train"].isdisjoint(paths["val"]))
        self.assertTrue(paths["train"].isdisjoint(paths["test"]))
        self.assertTrue(paths["val"].isdisjoint(paths["test"]))
        for split, samples in splits.items():
            labels = {label for _, label in samples}
            self.assertEqual(labels, {0, 1}, msg=f"{split} must contain all classes")

    def test_class_selection_defaults_to_every_dataset_class(self):
        class_names = ("pepper_healthy", "potato_blight", "tomato_healthy")
        with tempfile.TemporaryDirectory() as temporary_directory:
            dataset_root = Path(temporary_directory)
            for class_index, class_name in enumerate(class_names):
                class_directory = dataset_root / class_name
                class_directory.mkdir()
                for image_index in range(6):
                    color = (class_index * 70, image_index * 20, 180)
                    Image.new("RGB", (64, 64), color=color).save(class_directory / f"{image_index}.png")

            selected = collect_class_samples(
                dataset_root, class_names=None, max_per_class=8, seed=3
            )

        self.assertEqual(tuple(selected), class_names)
        self.assertEqual([len(selected[name]) for name in class_names], [6, 6, 6])


if __name__ == "__main__":
    unittest.main()
