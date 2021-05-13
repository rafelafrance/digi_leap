"""Handle OCR scores."""
import re
import string
import textwrap
from dataclasses import dataclass, field

import easyocr
import enchant
import pytesseract

import digi_leap.const
from digi_leap.const import CHAR_BLACKLIST, DATA_DIR
from digi_leap.util import to_opencv

MIN_WORDS = 20  # At least this many correctly spelled words should be in a label
OK = 60.0  # If this percent of words are spelled correctly it's considered good enough
MIN_LEN = 3  # Shorter words have a higher probability of being randomly generated

PUNCT = re.escape(string.punctuation)
SPLIT = re.compile(rf'([\s{PUNCT}]+)')

ALLOW = {'.)', '.]'}
LANG = 'en_US'
EXTRA_VOCAB = DATA_DIR / 'custom_vocab.txt'
VOCAB = enchant.DictWithPWL(LANG, str(EXTRA_VOCAB))

EASY_OCR = easyocr.Reader(['en'])


@dataclass(order=True)
class OCRScore:
    """Handle OCR scores."""

    found: int = 0
    total: int = 0
    file: str = ''
    stem: str = ''
    method: list[str] = field(default_factory=list)
    engine: str = ''
    text: str = ''

    @property
    def score(self):
        """Score the results."""
        return self.found, self.percent

    @property
    def is_ok(self):
        """Is the score good enough?"""
        return self.percent >= OK and self.found >= MIN_WORDS

    @property
    def percent(self):
        """Calculate the percent of found words."""
        per = self.found / self.total if self.total != 0 else 0.0
        return round(per * 100.0, 2)

    def __str__(self):
        return textwrap.dedent(f"""
        {self.score=}
        {self.found=}
        {self.percent=}
        {self.total=}
        {self.stem=}
        {self.method=}
        {self.engine=}
        """)

    def update(self, path, method):
        """Update the score."""
        self.file = str(path)
        self.stem = path.stem
        self.log(method)
        return self

    def log(self, action):
        """Log the OCR action."""
        if not self.method or action != self.method[-1]:
            self.method.append(action)


def score_tesseract(image):
    """Score the results of using the tesseract OCR engine."""
    text = pytesseract.image_to_string(image, config=digi_leap.const.TESS_CONFIG)
    return score_text(text, 'tesseract')


def score_easyocr(image):
    """Score the results of using the easyocr engine."""
    image = to_opencv(image)
    data = EASY_OCR.readtext(image, blocklist=CHAR_BLACKLIST)
    data = [d[1] for d in data]
    text = ' '.join(data)
    return score_text(text, 'easyocr')


def score_text(text, engine):
    """Score the output from the OCR."""
    text = re.sub(r'[\r\f]', '\n', text)
    text = re.sub(r'(\n\s*){3,}', '\n\n', text)
    text = text.strip()

    words = [x for w in SPLIT.split(text) if (x := w.strip())]

    found = sum(1 for w in words if len(w) >= MIN_LEN and VOCAB.check(w))

    return OCRScore(
        total=len(words),
        found=found,
        engine=engine,
        text=text,
    )
