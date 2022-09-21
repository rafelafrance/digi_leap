import logging
from argparse import Namespace

import torch
from torch.utils.data import DataLoader
from torch.utils.tensorboard import SummaryWriter
from tqdm import tqdm

from . import engine_utils
from ...db import db
from ..datasets.labeled_data_fasterrcnn import LabeledData
from ..models import model_utils
from .reference import engine


def train(model, args: Namespace):
    with db.connect(args.database) as cxn:
        run_id = db.insert_run(cxn, args)

        device = torch.device("cuda" if torch.has_cuda else "cpu")

        model_utils.load_model_state(model, args.load_model)
        model.to(device)

        writer = SummaryWriter(args.log_dir)

        train_loader = get_train_loader(cxn, args)
        val_loader = get_val_loader(cxn, args)
        optimizer = get_optimizer(model, args.learning_rate)

        start_epoch = 1  # model.state.get("epoch", 0) + 1
        end_epoch = start_epoch + args.epochs

        best_map = 0.0  # map = mAP = mean Average Precision

        logging.info("Training started.")

        for epoch in range(start_epoch, end_epoch):
            model.train()
            train_loss = one_epoch(model, device, train_loader, optimizer)

            model.eval()
            val_map = engine.evaluate(model, val_loader, device)
            val_map = val_map.coco_eval["bbox"].stats[0]

            best_map = save_checkpoint(
                model, optimizer, args.save_model, val_map, best_map, epoch
            )
            log_stats(writer, train_loss, val_map, best_map, epoch)

        writer.close()
        db.update_run_comments(cxn, run_id, comments(best_map))


def one_epoch(model, device, loader, optimizer=None):
    running_loss = 0.0

    for images, targets, *_ in tqdm(loader):
        images = list(image.to(device) for image in images)
        targets = [{k: v.to(device) for k, v in t.items()} for t in targets]

        losses = model(images, targets)
        losses = sum(loss for loss in losses.values())

        if optimizer:
            optimizer.zero_grad()
            losses.backward()
            optimizer.step()

        running_loss += losses.item()

    return running_loss / len(loader)


def get_optimizer(model, lr):
    return torch.optim.AdamW(model.parameters(), lr=lr)


def get_train_loader(cxn, args):
    logging.info("Loading training data.")
    raw_data = db.canned_select(
        cxn, "label_train_split", split="train", train_set=args.train_set
    )
    dataset = LabeledData(raw_data, args.image_size, augment=True, limit=args.limit)
    return DataLoader(
        dataset,
        batch_size=args.batch_size,
        num_workers=args.workers,
        shuffle=True,
        collate_fn=engine_utils.collate_fn_simple,
        pin_memory=True,
    )


def get_val_loader(cxn, args):
    logging.info("Loading validation data.")
    raw_data = db.canned_select(
        cxn, "label_train_split", split="val", train_set=args.train_set
    )
    dataset = LabeledData(raw_data, args.image_size, augment=False, limit=args.limit)
    return DataLoader(
        dataset,
        batch_size=args.batch_size,
        num_workers=args.workers,
        collate_fn=engine_utils.collate_fn_simple,
        pin_memory=True,
    )


def save_checkpoint(model, optimizer, save_model, val_map, best_map, epoch):
    if val_map >= best_map:
        best_map = val_map
        torch.save(
            {
                "epoch": epoch,
                "model_state": model.state_dict(),
                "optimizer_state": optimizer.state_dict(),
                "mAP": best_map,
            },
            save_model,
        )
    return best_map


def log_stats(writer, train_loss, val_map, best_map, epoch):
    logging.info(
        "%3d training loss %0.6f validation mAP %0.6f %s",
        epoch,
        train_loss,
        val_map,
        "++" if val_map == best_map else "",
    )
    writer.add_scalars(
        "Training vs. Validation",
        {
            "Training total loss": train_loss,
            "Validation total loss": val_map,
        },
        epoch,
    )
    writer.flush()


def comments(best_map):
    return f"Best validation: mAP {best_map:0.6f} "
