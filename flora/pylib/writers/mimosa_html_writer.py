from dataclasses import dataclass

from .. import const
from .base_html_writer import BaseHtmlWriter
from .base_html_writer import BaseHtmlWriterRow


# @dataclass(kw_only=True)
@dataclass
class HtmlWriterRow(BaseHtmlWriterRow):
    text_id: int = -1


class HtmlWriter(BaseHtmlWriter):
    def __init__(self, out_html):
        super().__init__(
            template_dir=f"{const.ROOT_DIR}/pylib/writers/templates",
            template="mimosa_html_writer.html",
            out_html=out_html,
        )

    def write(self, mimosa_rows, in_file_name=""):
        for i, mimosa_row in enumerate(mimosa_rows):
            text = self.format_text(mimosa_row)
            traits = self.format_traits(mimosa_row)
            self.formatted.append(
                HtmlWriterRow(
                    text_id=i,
                    formatted_text=text,
                    formatted_traits=traits,
                ),
            )

        self.write_template(in_file_name)
