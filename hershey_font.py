import xml.etree.ElementTree as ET
from pathlib import Path as FilePath
from svgpathtools import parse_path, Path

class SVGPathCommand:
    command: str
    args: list[float]

    def __init__(self, command: str, args: list[float]):
        self.command = command
        self.args = args

class Glyph:
    unicode: str
    width: float
    path: Path

    def __init__(self, unicode: str, width: float, path: str):
        self.unicode = unicode
        self.width = width
        self.commands = []

        self.path = parse_path(path if path != None else "")

class HersheyFont:
    glyphs: dict[str, Glyph]
    default_glyph: Glyph
    body_height: float
    name: str

    def __init__(self, file_path):

        tree = ET.parse(file_path)
        root = tree.getroot()

        ns = {"svg": "http://www.w3.org/2000/svg"}

        # get name from metadata tag
        font_name = None
        font_metadata = root.find(".//svg:metadata", ns)
        for line in font_metadata.text.splitlines():
            if line.startswith("Font name:"):
                font_name = line.split(":")[1].strip()
                break

        if font_name:
            self.name = font_name
        else: # fall back to using the font's file name
            self.name = FilePath(file_path).stem

        font_face = root.find(".//svg:font-face", ns)
        ascent = float(font_face.get("ascent"))
        descent = float(font_face.get("descent"))

        self.body_height = ascent - descent
        self.glyphs = {}
        for glyph in root.findall(".//svg:glyph", ns):
            unicode_char = glyph.attrib.get("unicode")
            width = float(glyph.attrib.get("horiz-adv-x"))
            path = glyph.attrib.get("d")

            self.glyphs[unicode_char] = Glyph(unicode_char, width, path)
        missing_glyph = root.find(".//svg:missing-glyph", ns)
        self.default_glyph = Glyph(None, float(missing_glyph.attrib.get("horiz-adv-x")), missing_glyph.attrib.get("d"))

    def get_or_default(self, char: str):
        glyph = self.glyphs.get(char)
        if glyph != None:
            return glyph
        return self.default_glyph 
            
