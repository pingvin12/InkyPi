import html
import logging
import re

from markupsafe import Markup

from plugins.base_plugin.base_plugin import BasePlugin

logger = logging.getLogger(__name__)


class Markdown(BasePlugin):
    def generate_settings_template(self):
        template_params = super().generate_settings_template()
        template_params["style_settings"] = True
        return template_params

    def generate_image(self, settings, device_config):
        markdown_input = settings.get("markdown_input", "")
        if not markdown_input.strip():
            raise RuntimeError("Markdown input is required.")

        dimensions = device_config.get_resolution()
        if device_config.get_config("orientation") == "vertical":
            dimensions = dimensions[::-1]

        template_params = {
            "plugin_settings": settings,
            "markdown_html": Markup(self._markdown_to_html(markdown_input)),
        }

        image = self.render_image(dimensions, "markdown.html", "markdown.css", template_params)
        if not image:
            raise RuntimeError("Unable to render markdown image.")

        return image

    def _render_inline(self, text):
        escaped = html.escape(text)

        escaped = re.sub(
            r"!\[([^\]]*)\]\(([^)\s]+)\)",
            r'<img src="\2" alt="\1">',
            escaped,
        )
        escaped = re.sub(
            r"\[([^\]]+)\]\(([^)\s]+)\)",
            r'<a href="\2">\1</a>',
            escaped,
        )

        escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
        escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", escaped)
        escaped = re.sub(r"_([^_]+)_", r"<em>\1</em>", escaped)
        escaped = re.sub(r"~~([^~]+)~~", r"<del>\1</del>", escaped)

        return escaped

    def _markdown_to_html(self, markdown_input):
        lines = markdown_input.splitlines()
        output = []
        in_ul = False
        in_ol = False

        def close_lists():
            nonlocal in_ul, in_ol
            if in_ul:
                output.append("</ul>")
                in_ul = False
            if in_ol:
                output.append("</ol>")
                in_ol = False

        for raw_line in lines:
            line = raw_line.rstrip()
            stripped = line.strip()

            if not stripped:
                close_lists()
                continue

            heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if heading:
                close_lists()
                level = len(heading.group(1))
                content = self._render_inline(heading.group(2))
                output.append(f"<h{level}>{content}</h{level}>")
                continue

            bullet = re.match(r"^[-*+]\s+(.*)$", stripped)
            if bullet:
                if in_ol:
                    output.append("</ol>")
                    in_ol = False
                if not in_ul:
                    output.append("<ul>")
                    in_ul = True
                output.append(f"<li>{self._render_inline(bullet.group(1))}</li>")
                continue

            ordered = re.match(r"^\d+\.\s+(.*)$", stripped)
            if ordered:
                if in_ul:
                    output.append("</ul>")
                    in_ul = False
                if not in_ol:
                    output.append("<ol>")
                    in_ol = True
                output.append(f"<li>{self._render_inline(ordered.group(1))}</li>")
                continue

            quote = re.match(r"^>\s?(.*)$", stripped)
            if quote:
                close_lists()
                output.append(f"<blockquote>{self._render_inline(quote.group(1))}</blockquote>")
                continue

            close_lists()
            output.append(f"<p>{self._render_inline(stripped)}</p>")

        close_lists()
        return "\n".join(output)
