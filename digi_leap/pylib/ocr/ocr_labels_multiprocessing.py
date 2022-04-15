"""OCR a set of labels."""
import argparse
import multiprocessing
import warnings
from collections import defaultdict
from itertools import chain
from multiprocessing import Pool

from PIL import Image
from tqdm import tqdm

from . import engine_runner
from . import label_transformer as lt
from .. import db
from .. import utils

ENGINE = {
    "tesseract": engine_runner.tesseract_engine,
    "easy": engine_runner.easyocr_engine,
}


def ocr_labels(args: argparse.Namespace) -> None:
    with db.connect(args.database) as cxn:
        run_id = db.insert_run(cxn, args)

        multiprocessing.set_start_method("spawn")

        db.execute(cxn, "delete from ocr where ocr_set = ?", (args.ocr_set,))
        db.create_ocr_table(cxn)

        sheets = get_sheet_labels(cxn, args.classes, args.label_set, args.label_conf)

        batches = utils.dict_chunks(sheets, args.batch_size)

        results = []
        with Pool(processes=args.workers) as pool, tqdm(total=len(batches)) as bar:
            for batch in batches:
                results.append(
                    pool.apply_async(
                        ocr_batch,
                        args=(batch, args.pipelines, args.ocr_engines, args.ocr_set),
                        callback=lambda _: bar.update(),
                    )
                )
            results = [r.get() for r in results]

        results = list(chain(*list(results)))

        db.insert_ocr(cxn, results)
        db.update_run_finished(cxn, run_id)


def ocr_batch(sheets, pipelines, ocr_engines, ocr_set) -> list[dict]:
    batch: list[dict] = []

    with warnings.catch_warnings():  # Turn off EXIF warnings
        warnings.filterwarnings("ignore", category=UserWarning)

        for path, labels in sheets.items():
            sheet = Image.open(path)

            for lb in labels:
                label = sheet.crop(
                    (
                        lb["label_left"],
                        lb["label_top"],
                        lb["label_right"],
                        lb["label_bottom"],
                    )
                )

                for pipeline in pipelines:
                    image = lt.transform_label(pipeline, label)

                    for engine in ocr_engines:
                        results = [r for r in ENGINE[engine](image) if r["ocr_text"]]
                        for result in results:
                            batch.append(
                                result
                                | {
                                    "label_id": lb["label_id"],
                                    "ocr_set": ocr_set,
                                    "engine": engine,
                                    "pipeline": pipeline,
                                }
                            )
    return batch


def get_sheet_labels(cxn, classes, label_set, label_conf) -> dict:
    sheets = defaultdict(list)

    labels = db.select_labels(cxn, label_set=label_set)

    if classes:
        labels = [lb for lb in labels if lb["class"] in classes]

    labels = [lb for lb in labels if lb["label_conf"] >= label_conf]

    for label in labels:
        sheets[label["path"]].append(label)

    return sheets