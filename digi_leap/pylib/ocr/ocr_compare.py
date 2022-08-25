import json
import warnings
from copy import copy
from itertools import chain
from itertools import combinations
from multiprocessing import Pool

import cppimport.import_hook  # noqa pylint: disable=unused-import
import pandas as pd
from PIL import Image
from tqdm import tqdm

from . import label_transformer
from . import ocr_runner
from .. import consts
from ..db import db
from ..label_builder import label_builder
from ..label_builder.line_align import char_sub_matrix as subs
from ..label_builder.line_align import line_align_py  # noqa
from ..label_builder.spell_well.spell_well import SpellWell

IMAGE_TRANSFORMS = ["", "deskew", "binarize", "denoise"]


def ocr(gold_std):
    golden = []
    for gold in tqdm(gold_std, desc="ocr"):

        gold["gold_text"] = " ".join(gold["gold_text"].split())
        gold["pipe_text"]: dict[tuple[str, str], str] = {}

        original = get_label(gold)
        for transform in IMAGE_TRANSFORMS:
            image = transform_image(original, transform)

            text = ocr_runner.easy_text(image)
            gold["pipe_text"][f"[{transform}, easyocr]"] = " ".join(text.split())

            text = ocr_runner.tess_text(image)
            gold["pipe_text"][f"[{transform}, tesseract]"] = " ".join(text.split())

        golden.append(gold)
    return golden


def score(golden, score_set, gold_set, processes=8, chunk=10):
    batches = [golden[i : i + chunk] for i in range(0, len(golden), chunk)]
    scores, results = [], []

    with Pool(processes=processes) as pool, tqdm(total=len(batches)) as bar:
        for batch in batches:
            results.append(
                pool.apply_async(
                    score_batch,
                    args=(batch, score_set, gold_set),
                    callback=lambda _: bar.update(),
                )
            )
        scores = [r.get() for r in results]
        scores = list(chain(*list(scores)))

    return scores


def score_batch(golden, score_set, gold_set) -> list[dict]:
    scores: list[dict] = []
    pipelines = get_pipelines(golden[0])

    matrix = subs.select_char_sub_matrix(char_set="default")
    line_align = line_align_py.LineAlign(matrix)
    spell_well = SpellWell()

    for gold in golden:
        for pipes in pipelines:
            pipeline = copy(pipes)

            lines = [gold["pipe_text"][p] for p in pipeline]
            lines = label_builder.filter_sort_lines(lines, line_align)

            aligned = line_align.align(lines)

            # Pipeline without post-processing
            text = label_builder.consensus(aligned)
            scores.append(
                score_rec(gold, text, pipeline, score_set, gold_set, line_align)
            )

            # Pipeline with post-processing
            text = label_builder.post_process_text(text, spell_well)
            pipeline.append("[post_process]")
            scores.append(
                score_rec(gold, text, pipeline, score_set, gold_set, line_align)
            )

    return scores


def insert_scores(scores, database, score_set):
    with db.connect(database) as cxn:
        db.execute(cxn, "delete from ocr_scores where score_set = ?", (score_set,))
        db.canned_insert("ocr_scores", cxn, scores)


def select_scores(database, score_set):
    with db.connect(database) as cxn:
        results = db.execute(
            cxn, "select * from ocr_scores where score_set = ?", (score_set,)
        )
        scores = [dict(r) for r in results]
    return scores


def score_rec(gold, text, pipeline, score_set, gold_set, line_align):
    text = text.replace("⋄", "")  # Remove gaps
    return {
        "score_set": score_set,
        "label_id": gold["label_id"],
        "gold_id": gold["gold_id"],
        "gold_set": gold_set,
        "pipeline": json.dumps(pipeline),
        "score_text": text,
        "score": line_align.levenshtein(gold["gold_text"], text),
    }


def get_pipelines(gold) -> list[list[str]]:
    pipelines = []
    keys = sorted(gold["pipe_text"].keys())
    for r in range(1, len(keys) + 1):
        pipelines += [list(c) for c in combinations(keys, r)]
    return pipelines


def get_label(gold: dict):
    with warnings.catch_warnings():  # Turn off EXIF warnings
        warnings.filterwarnings("ignore", category=UserWarning)
        path = consts.ROOT_DIR / gold["path"]
        sheet = Image.open(path)
        label = sheet.crop(
            (
                gold["label_left"],
                gold["label_top"],
                gold["label_right"],
                gold["label_bottom"],
            )
        )
    return label


def transform_image(image, transform):
    if not transform:
        return image
    return label_transformer.transform_label(transform, image)


# ##################################################################################
def select_gold_std(database, gold_set):
    sql = """
        select *
        from gold_standard
        join labels using (label_id)
        join sheets using (sheet_id)
        where gold_set = ?
        """
    with db.connect(database) as cxn:
        gold = cxn.execute(sql, (gold_set,))
    return [dict(r) for r in gold]


def insert_gold_std(csv_path, database, gold_set):
    df = pd.read_csv(csv_path).fillna("")
    df = df.loc[df.gold_text != ""]

    df["label_id"] = df["label"].str.split("_").str[2]
    df["label_id"] = df["label_id"].str.split(".").str[0].astype(int)

    df["sheet_id"] = df["label"].str.split("_").str[1]

    df["gold_set"] = gold_set

    df = df.drop(["sheet", "label"], axis="columns")

    with db.connect(database) as cxn:
        df.to_sql("gold_standard", cxn, if_exists="append", index=False)
