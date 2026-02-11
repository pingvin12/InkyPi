import logging
import os
import textwrap

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub
from PIL import Image, ImageDraw, ImageFont

from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)

WIDTH = 800
HEIGHT = 480
PAGE_MARGIN = 40
LINE_SPACING = 8
DEFAULT_FONT_SIZE = 28
DEFAULT_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"

# Inky 7-color (black, white, green, blue, red, yellow, orange)
INKY_7_COLOR_PALETTE = [
    (0, 0, 0),
    (255, 255, 255),
    (0, 255, 0),
    (0, 0, 255),
    (255, 0, 0),
    (255, 255, 0),
    (255, 165, 0),
]


class EpubReader(BasePlugin):
    def generate_image(self, settings, device_config):
        epub_path = settings.get("epubFile")
        if not epub_path:
            raise RuntimeError("Upload an EPUB file to render.")

        if not os.path.exists(epub_path):
            raise RuntimeError("The selected EPUB file no longer exists. Re-upload it and try again.")

        try:
            font_size = int(settings.get("fontSize", DEFAULT_FONT_SIZE))
        except (TypeError, ValueError):
            font_size = DEFAULT_FONT_SIZE

        text_content = self._extract_text_in_reading_order(epub_path)
        pages = self._paginate_text(text_content, font_size=font_size)
        if not pages:
            raise RuntimeError("No readable text was found in this EPUB.")

        page_index = int(settings.get("pageIndex", 0))
        if page_index >= len(pages):
            page_index = 0

        page_text = pages[page_index]
        settings["pageIndex"] = (page_index + 1) % len(pages)

        image = self._render_page(page_text, font_size=font_size)
        return self._convert_to_inky_palette(image)

    def _extract_text_in_reading_order(self, epub_path):
        book = epub.read_epub(epub_path)
        text_content = []

        for spine_item in book.spine:
            item_id = spine_item[0]
            item = book.get_item_with_id(item_id)

            if not item or item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue

            soup = BeautifulSoup(item.get_content(), "html.parser")
            text = soup.get_text(separator=" ", strip=True)
            if text:
                text_content.append(text)

        if not text_content:
            # Fallback for malformed EPUB spine entries
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_DOCUMENT:
                    soup = BeautifulSoup(item.get_content(), "html.parser")
                    text = soup.get_text(separator=" ", strip=True)
                    if text:
                        text_content.append(text)

        return "\n\n".join(text_content)

    def _paginate_text(self, text, font_size):
        if not text.strip():
            return []

        font = self._load_font(font_size)
        lines_per_page = max(1, (HEIGHT - (PAGE_MARGIN * 2)) // (font_size + LINE_SPACING))
        char_width = max(1, int(font_size * 0.58))
        chars_per_line = max(1, (WIDTH - (PAGE_MARGIN * 2)) // char_width)

        wrapped_lines = textwrap.wrap(
            text,
            width=chars_per_line,
            replace_whitespace=True,
            drop_whitespace=True,
        )

        pages = []
        for i in range(0, len(wrapped_lines), lines_per_page):
            page_lines = wrapped_lines[i:i + lines_per_page]
            pages.append("\n".join(page_lines))

        return pages

    def _render_page(self, text, font_size):
        image = Image.new("RGB", (WIDTH, HEIGHT), "white")
        draw = ImageDraw.Draw(image)
        font = self._load_font(font_size)

        draw.multiline_text(
            (PAGE_MARGIN, PAGE_MARGIN),
            text,
            font=font,
            fill="black",
            spacing=LINE_SPACING,
        )
        return image

    def _load_font(self, font_size):
        try:
            return ImageFont.truetype(DEFAULT_FONT_PATH, font_size)
        except OSError:
            logger.warning("Could not load %s, using default PIL font.", DEFAULT_FONT_PATH)
            return ImageFont.load_default()

    def _convert_to_inky_palette(self, image):
        palette_image = Image.new("P", (1, 1))
        palette = []
        for color in INKY_7_COLOR_PALETTE:
            palette.extend(color)

        # Pad palette to 256 colors (768 values)
        palette.extend([0] * (768 - len(palette)))
        palette_image.putpalette(palette)

        return image.convert("RGB").quantize(palette=palette_image, dither=Image.Dither.FLOYDSTEINBERG)
