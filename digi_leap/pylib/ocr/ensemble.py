from . import label_transformer as lt
from . import ocr_runner
from ..builder import label_builder
from ..builder.line_align import char_sub_matrix as subs
from ..builder.line_align import line_align_py  # noqa
from ..builder.spell_well import SpellWell


class Ensemble:
    all_pipes = {
        "none_easyocr": "[,easyocr]",
        "none_tesseract": "[,tesseract]",
        "deskew_easyocr": "[deskew,easyocr]",
        "deskew_tesseract": "[deskew,tesseract]",
        "binarize_easyocr": "[binarize,easyocr]",
        "binarize_tesseract": "[binarize,tesseract]",
        "denoise_easyocr": "[denoise,easyocr]",
        "denoise_tesseract": "[denoise,tesseract]",
        "pre_process": "[pre_process]",
        "post_process": "[post_process]",
    }

    def __init__(self, **kwargs):
        self.pipes = {k for k in self.all_pipes.keys() if kwargs.get(k, False)}
        if not self.pipes:
            raise ValueError("No pipes given")

        matrix = subs.select_char_sub_matrix(char_set="default")
        self.line_align = line_align_py.LineAlign(matrix)
        self.spell_well = SpellWell()

    @property
    def needs_denoise(self):
        return any(1 for p in self.pipes if p.startswith("denoise"))

    @property
    def needs_deskew(self):
        return any(1 for p in self.pipes if p.startswith("deskew"))

    @property
    def needs_binarize(self):
        return any(1 for p in self.pipes if p.startswith("binarize"))

    @property
    def pipeline(self):
        pipes = [v for k, v in self.all_pipes.items() if k in self.pipes]
        return ",".join(pipes)

    async def run(self, image):
        lines = [ln for ln in await self.ocr(image)]
        lines = label_builder.filter_lines(lines, self.line_align)
        text = self.line_align.align(lines)
        text = label_builder.consensus(text)
        if "post_process" in self.pipes:
            text = label_builder.post_process_text(text, self.spell_well)
        return text

    async def ocr(self, image):
        deskew = lt.transform_label("deskew", image) if self.needs_deskew else None
        binary = lt.transform_label("binarize", image) if self.needs_binarize else None
        denoise = lt.transform_label("denoise", image) if self.needs_denoise else None

        pre_process = "preprocess" in self.pipes

        lines = []
        if "none_easyocr" in self.pipes:
            lines.append(await ocr_runner.easy_text(image, pre_process=pre_process))
        if "none_tesseract" in self.pipes:
            lines.append(await ocr_runner.tess_text(image, pre_process=pre_process))
        if "deskew_easyocr" in self.pipes:
            lines.append(await ocr_runner.easy_text(deskew, pre_process=pre_process))
        if "deskew_tesseract" in self.pipes:
            lines.append(await ocr_runner.tess_text(deskew, pre_process=pre_process))
        if "binarize_easyocr" in self.pipes:
            lines.append(await ocr_runner.easy_text(binary, pre_process=pre_process))
        if "binarize_tesseract" in self.pipes:
            lines.append(await ocr_runner.tess_text(binary, pre_process=pre_process))
        if "denoise_easyocr" in self.pipes:
            lines.append(await ocr_runner.easy_text(denoise, pre_process=pre_process))
        if "denoise_tesseract" in self.pipes:
            lines.append(await ocr_runner.tess_text(denoise, pre_process=pre_process))
        return lines