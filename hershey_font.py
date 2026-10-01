import xml.etree.ElementTree as ET
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

    def __init__(self, unicode: str, width: float, path: str, scale: float = 1.0):
        self.unicode = unicode
        self.width = width * scale
        self.commands = []

        self.path = parse_path(path if path != None else "").scaled(scale)

class HersheyFont:
    glyphs: dict[str, Glyph]
    default_glyph: Glyph
    body_height: float

    def __init__(self, file_path, max_body_height: float = 25):
        tree = ET.parse(file_path)
        root = tree.getroot()

        ns = {"svg": "http://www.w3.org/2000/svg"}

        font_face = root.find(".//svg:font-face", ns)
        ascent = float(font_face.get("ascent"))
        descent = float(font_face.get("descent"))
        scale = max_body_height / (ascent - descent)

        self.body_height = max_body_height # todo: right now it's in mm, later change to using pt units
        self.glyphs = {}
        for glyph in root.findall(".//svg:glyph", ns):
            unicode_char = glyph.attrib.get("unicode")
            width = float(glyph.attrib.get("horiz-adv-x"))
            path = glyph.attrib.get("d")

            self.glyphs[unicode_char] = Glyph(unicode_char, width, path, scale)
        missing_glyph = root.find(".//svg:missing-glyph", ns)
        self.default_glyph = Glyph(None, float(missing_glyph.attrib.get("horiz-adv-x")), missing_glyph.attrib.get("d"), scale)

    def get_or_default(self, char: str):
        glyph = self.glyphs.get(char)
        if glyph != None:
            return glyph
        return self.default_glyph 
            
