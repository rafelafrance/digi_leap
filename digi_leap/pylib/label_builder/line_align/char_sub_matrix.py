import numpy as np
from PIL import Image
from PIL import ImageDraw
from tqdm import tqdm

from ...db import db


class Char:
    def __init__(self, char, image_size, font):
        self.char = char
        self.pix = self.char_pix()
        self.h, self.w = self.char_size()
        self.image_size = image_size
        self.font = font

    def char_pix(self):
        """Put char pixels into a matrix."""
        image = Image.new("L", (self.image_size, self.image_size), color="black")
        draw = ImageDraw.Draw(image)
        draw.text((0, 0), self.char, font=self.font, anchor="lt", fill="white")
        pix = np.asarray(image) > 128
        pix = pix.astype("float")
        return pix

    def char_size(self):
        """Get the size of the char image."""
        nz = np.nonzero(self.pix)
        h = np.max(nz[0]) - np.min(nz[0]) + 1
        w = np.max(nz[1]) - np.min(nz[1]) + 1
        return h, w

    def center(self):
        """Move a char image to the center of the image."""
        y = (self.pix.shape[0] - self.h) // 2
        x = (self.pix.shape[1] - self.w) // 2
        self.pix = np.roll(self.pix, (y, x), axis=(0, 1))


# #####################################################################################
def add_chars(args):
    """Add characters to the character substitution matrix."""
    with db.connect(args.database) as cxn:
        run_id = db.insert_run(cxn, args)

        matrix = select_matrix(cxn, args.char_set)

        old_chars = {k[0] for k in matrix.keys()}
        old_chars |= {k[1] for k in matrix.keys()}

        new_chars = set(args.chars)

        calc_scores(old_chars, new_chars, matrix, args.image_size, args.font)
        insert_matrix(cxn, matrix, args.char_set)

        db.update_run_finished(cxn, run_id)


def select_matrix(cxn, char_set):
    sql = """select * from char_sub_matrix where char_set = ?"""
    rows = db.execute(cxn, sql, (char_set,))
    matrix = {}
    for row in rows:
        char1, char2 = row["char1"], row["char2"]
        if char1 > char2:
            char1, char2 = char2, char1
        matrix[(char1, char2)] = dict(row)
    return matrix


def insert_matrix(cxn, matrix, char_set):
    batch = [
        {
            "char1": c1,
            "char2": c2,
            "char_set": char_set,
            "score": rec["score"],
            "sub": rec["sub"],
        }
        for (c1, c2), rec in matrix.items()
    ]
    db.execute(cxn, "delete from char_sub_matrix where char_set = ?", (char_set,))
    db.canned_insert("char_sub_matrix", cxn, batch)


def calc_scores(old_chars, new_chars, matrix, image_size, font):
    """Calculate character substitution values.

    Substitution values go from 2 to -2. The cutoff values for converting a scores into
    substitution values are magic constants.
    """
    all_chars = [Char(c, image_size, font) for c in sorted(old_chars | new_chars)]

    for i, char1 in tqdm(enumerate(all_chars)):
        char1.center()

        for char2 in all_chars[i:]:
            if char1.char not in new_chars and char2.char not in new_chars:
                score = matrix[(char1, char2)]["score"]
                sub = matrix[(char1, char2)]["sub"]
            elif char1 == char2:
                score = None
                sub = 2.0
            elif char1.char == " " or char2.char == " ":
                score = np.sum(char2.pix)
                sub = -1.0 if score < 20 else -2.0  # MAGIC TODO
            else:
                score = get_max_iou(char1.pix, char2.pix)
                sub = get_sub(score)

            matrix[(char1, char2)] = {"score": score, "sub": sub}


def get_sub(score):
    # These values are all MAGIC TODO
    if score >= 0.7:
        sub = 1.0
    elif score >= 0.5:
        sub = 0.0
    elif score >= 0.4:
        sub = -1.0
    else:
        sub = -2.0
    return sub


def get_max_iou(pix1, pix2):
    """Get the max IOU of the two chars."""
    max_iou = 0.0
    for y in range(pix2.shape[0]):
        for x in range(pix2.shape[1]):
            rolled = np.roll(pix2, (y, x), axis=(0, 1))
            overlap = pix1 + rolled
            union = np.sum(overlap > 0.0)
            inter = np.sum(overlap == 2.0)
            curr_iou = inter / union if union else 0.0
            max_iou = max(max_iou, curr_iou)
    return max_iou


# #####################################################################################
def select_char_sub_matrix(database, char_set):
    with db.connect(database) as cxn:
        sql = """select * from char_sub_matrix where char_set = ?"""
        rows = [dict(r) for r in db.execute(cxn, sql, (char_set,))]
        matrix = {f'{r["char1"]}{r["char2"]}': r["sub"] for r in rows}
        return matrix
