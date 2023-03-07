from traiter.pylib import tokenizer
from traiter.pylib import tokenizer_util

from .patterns import term_patterns as terms


INFIX = [
    r"(?<=[0-9])[/,](?=[0-9])",  # digit,digit
    r"(?<=[A-Z])[/-](?=[0-9])",  # letter-digit
    "-_",
]


def setup_tokenizer(nlp):
    tokenizer_util.remove_special_case(nlp, terms.TERMS1)
    tokenizer_util.remove_special_case(nlp, terms.TERMS2)
    tokenizer_util.append_prefix_regex(nlp)
    tokenizer_util.append_infix_regex(nlp, INFIX)
    tokenizer_util.append_suffix_regex(nlp)
    tokenizer_util.append_abbrevs(nlp, tokenizer.ABBREVS)
