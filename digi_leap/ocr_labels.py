#!/usr/bin/env python3
import argparse
import textwrap
from pathlib import Path

from pylib import consts
from pylib.ocr import ocr_labels
from traiter import log


def main():
    log.started()
    args = parse_args()
    ocr_labels.ocr_labels(args)
    log.finished()


def parse_args() -> argparse.Namespace:
    # The current best ensemble
    # [[, easyocr], [, tesseract], [deskew, easyocr], [deskew, tesseract],
    # [binarize, tesseract], [denoise, tesseract], [post_process]]
    description = """OCR images of labels. (Try this ensemble: -RrDdbnp)"""

    arg_parser = argparse.ArgumentParser(
        description=textwrap.dedent(description), fromfile_prefix_chars="@"
    )

    arg_parser.add_argument(
        "--database",
        required=True,
        type=Path,
        metavar="PATH",
        help="""Path to a digi-leap database.""",
    )

    arg_parser.add_argument(
        "--ocr-set",
        required=True,
        metavar="NAME",
        help="""Name this OCR set.""",
    )

    arg_parser.add_argument(
        "--label-set",
        required=True,
        metavar="NAME",
        help="""Create this label set.""",
    )

    arg_parser.add_argument(
        "--classes",
        choices=consts.CLASSES[1:],
        default=["Typewritten"],
        type=str,
        nargs="*",
        help="""Keep labels if they fall into any of these categories.
            (default: %(default)s)""",
    )

    arg_parser.add_argument(
        "--label-conf",
        type=float,
        default=0.25,
        help="""Only OCR labels that have a confidence >= to this. Set it to 0.0 to
            get all of the labels. (default: %(default)s)""",
    )

    arg_parser.add_argument(
        "-R",
        "--none-easyocr",
        action="store_true",
        help="""Add a step to the OCR pipeline that runs EasyOCR without image
            manipulation.""",
    )

    arg_parser.add_argument(
        "-r",
        "--none-tesseract",
        action="store_true",
        help="""Add a step to the OCR pipeline that runs Tesseract without image
            manipulation.""",
    )

    arg_parser.add_argument(
        "-D",
        "--deskew-easyocr",
        action="store_true",
        help="""Add a step to the OCR pipeline that deskews the label image before
            running EasyOCR.""",
    )

    arg_parser.add_argument(
        "-d",
        "--deskew-tesseract",
        action="store_true",
        help="""Add a step to the OCR pipeline that deskews the label image before
            running Tesseract.""",
    )

    arg_parser.add_argument(
        "-B",
        "--binarize-easyocr",
        action="store_true",
        help="""Add a step to the OCR pipeline that binarizes the label image before
            running EasyOCR.""",
    )

    arg_parser.add_argument(
        "--binarize-tesseract",
        "-b",
        action="store_true",
        help="""Add a step to the OCR pipeline that binarizes the label image before
            running Tesseract.""",
    )

    arg_parser.add_argument(
        "--denoise-easyocr",
        "-N",
        action="store_true",
        help="""Add a step to the OCR pipeline that denoises the label image before
            running EasyOCR.""",
    )

    arg_parser.add_argument(
        "-n",
        "--denoise-tesseract",
        action="store_true",
        help="""Add a step to the OCR pipeline that denoises the label image before
            running Tesseract.""",
    )

    arg_parser.add_argument(
        "-p",
        "--post-process",
        action="store_true",
        help="""Add a step to the OCR pipeline that post-processes the OCR text
            sequence with a spell checker etc.""",
    )

    arg_parser.add_argument(
        "--notes",
        default="",
        metavar="TEXT",
        help="""Notes about this run. Enclose them in quotes.""",
    )

    args = arg_parser.parse_args()
    return args


if __name__ == "__main__":
    main()
