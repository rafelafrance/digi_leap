#!/usr/bin/env python
"""Train a model to recognize digits on allometry sheets."""

import argparse
import logging
import textwrap
from os import makedirs
from pathlib import Path
from random import randint

import torch
import torchvision
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torchvision.ops import batched_nms

from digi_leap.faster_rcnn_data import FasterRcnnData
from digi_leap.log import finished, started
from digi_leap.mean_avg_precision import mAP
from digi_leap.subject import CLASSES
from digi_leap.util import collate_fn


def train(args):
    """Train the neural net."""
    # make_dirs(args)

    state = torch.load(args.load_model) if args.load_model else {}

    model = get_model()
    if state.get("model_state"):
        model.load_state_dict(state["model_state"])

    device = torch.device(args.device)
    model.to(device)

    params = [p for p in model.parameters() if p.requires_grad]

    # optimizer = torch.optim.Adam(model.parameters(), lr=args.learning_rate)
    optimizer = torch.optim.SGD(
        params, lr=args.learning_rate, momentum=0.9, weight_decay=0.0005
    )
    if state.get("optimizer_state"):
        optimizer.load_state_dict(state["optimizer_state"])

    lr_scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=3)

    train_loader, score_loader = get_loaders(args)

    start_epoch = state["epoch"] + 1 if state.get("epoch") else 1
    end_epoch = start_epoch + args.epochs + 1

    best_score = state["best_score"] if state.get("best_score") else -1.0

    for epoch in range(start_epoch, end_epoch):
        train_loss = train_epoch(model, train_loader, device, optimizer)

        lr_scheduler.step()

        score = score_epoch(model, score_loader, device)

        log_results(epoch, train_loss, score, best_score)

        best_score = save_model(
            model, optimizer, epoch, score, best_score, args.save_model
        )


def train_epoch(model, loader, device, optimizer):
    """Train for one epoch."""
    model.train()

    running_loss = 0.0
    count = 0

    for images, targets in loader:
        count += len(targets)

        images = list(image.to(device) for image in images)
        targets = [{k: v.to(device) for k, v in t.items()} for t in targets]

        loss_dict = model(images, targets)
        losses = sum(loss for loss in loss_dict.values())
        loss_value = losses.item()
        running_loss += loss_value

        optimizer.zero_grad()
        losses.backward()
        optimizer.step()

    return running_loss / count


def score_epoch(model, loader, device, iou_threshold=0.3):
    """Evaluate the model."""
    model.eval()

    all_results = []

    for images, targets in loader:
        images = list(image.to(device) for image in images)

        preds = model(images, targets)

        for pred, target in zip(preds, targets):
            idx = batched_nms(
                pred["boxes"], pred["scores"], pred["labels"], iou_threshold
            )
            all_results.append(
                {
                    "image_id": target["image_id"],
                    "true_boxes": target["boxes"],
                    "true_labels": target["labels"],
                    "pred_boxes": pred["boxes"][idx, :].detach().cpu(),
                    "pred_labels": pred["labels"][idx].detach().cpu(),
                    "pred_scores": pred["scores"][idx].detach().cpu(),
                }
            )

    score = mAP(all_results)

    return score


def log_results(epoch, train_loss, score, best_score):
    """Print results to screen."""
    new = "*" if score > best_score else ""
    logging.info(
        f"""Epoch {epoch} Loss train: {train_loss:0.3f}, mAP: {score:0.3f} {new}"""
    )


def save_model(model, optimizer, epoch, score, best_score, save_model):
    """Save the current model if it scores well."""
    if score > best_score:
        torch.save(
            {
                "epoch": epoch,
                "modeL_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
                "best_score": score,
            },
            save_model,
        )
        return score
    return best_score


def get_loaders(args):
    """Get the data loaders."""
    subjects = FasterRcnnData.read_jsonl(args.reconciled_jsonl)

    if args.limit:
        subjects = subjects[: args.limit]

    train_subjects, score_subjects = train_test_split(
        subjects, test_size=args.split, random_state=args.seed
    )
    train_dataset = FasterRcnnData(train_subjects, args.image_dir)
    score_dataset = FasterRcnnData(score_subjects, args.image_dir)

    train_loader = DataLoader(
        train_dataset,
        shuffle=True,
        batch_size=args.batch_size,
        num_workers=args.workers,
        collate_fn=collate_fn,
    )

    score_loader = DataLoader(
        score_dataset,
        shuffle=True,
        batch_size=args.batch_size,
        num_workers=args.workers,
        collate_fn=collate_fn,
    )

    return train_loader, score_loader


def make_dirs(args):
    """Create output directories."""
    if args.model_dir:
        makedirs(args.model_dir, exist_ok=True)


def get_model():
    """Get the model to use."""
    model = torchvision.models.detection.fasterrcnn_resnet50_fpn(pretrained=True)
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(
        in_features, num_classes=len(CLASSES) + 1
    )
    return model


def parse_args():
    """Process command-line arguments."""
    description = """Train a model to find labels on herbarium sheets."""
    arg_parser = argparse.ArgumentParser(
        description=textwrap.dedent(description), fromfile_prefix_chars="@"
    )

    arg_parser.add_argument(
        "--reconciled-jsonl",
        required=True,
        type=Path,
        help="""The JSONL file containing reconciled bounding boxes.""",
    )

    arg_parser.add_argument(
        "--image-dir",
        required=True,
        type=Path,
        help="""Read training images corresponding to the JSONL file from this
            directory.""",
    )

    arg_parser.add_argument(
        "--save-model",
        type=Path,
        required=True,
        help="""Save model state to this file.""",
    )

    arg_parser.add_argument(
        "--load-model",
        type=Path,
        help="""Load this model state to continue training.""",
    )

    arg_parser.add_argument(
        "--split",
        type=float,
        default=0.25,
        help="""Fraction of subjects in the score dataset. (default: %(default)s)""",
    )

    default = "cuda:0" if torch.cuda.is_available() else "cpu"
    arg_parser.add_argument(
        "--device",
        default=default,
        help="""Which GPU or CPU to use. Options are 'cpu', 'cuda:0', 'cuda:1' etc.
            (default: %(default)s)""",
    )

    arg_parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="""How many epochs to train. (default: %(default)s)""",
    )

    arg_parser.add_argument(
        "--learning-rate",
        type=float,
        default=0.005,
        help="""Initial learning rate. (default: %(default)s)""",
    )

    arg_parser.add_argument(
        "--batch-size",
        type=int,
        default=2,
        help="""Input batch size. (default: %(default)s)""",
    )

    arg_parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="""Number of workers for loading data. (default: %(default)s)""",
    )

    arg_parser.add_argument(
        "--limit",
        type=int,
        help="""Limit the input to this many records.""",
    )

    arg_parser.add_argument("--seed", type=int, help="""Create a random seed.""")

    args = arg_parser.parse_args()

    args.seed = args.seed if args.seed is not None else randint(0, 4_000_000_000)

    return args


if __name__ == "__main__":
    started()

    ARGS = parse_args()
    train(ARGS)

    finished()
