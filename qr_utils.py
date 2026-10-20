"""Etiquetas de QR Code com código seguro, sem dados pessoais expostos."""
from io import BytesIO
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import qrcode
from PIL import Image, ImageDraw, ImageFont


def qr_target(code: str, public_url: str = "") -> tuple[str, bool]:
    """URL pública para abrir o registro ou texto curto quando não há URL."""
    url = public_url.strip()
    if url:
        parsed = urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Insira um endereço válido começando com https:// ou http://.")
        params = dict(parse_qsl(parsed.query, keep_blank_values=True))
        params["doc"] = code
        return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(params), "")), True
    return f"FIND DOC SCHOOL | {code} | Procure este código no site FDS", False


def make_qr_png(code: str, public_url: str = "") -> bytes:
    payload, _ = qr_target(code, public_url)
    img = qrcode.make(payload, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=3).convert("RGB")
    stream = BytesIO()
    img.save(stream, format="PNG")
    return stream.getvalue()


def make_label_png(code: str, title: str, place: str, public_url: str = "") -> bytes:
    image = Image.new("RGB", (850, 360), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((9, 9, 840, 350), radius=22, outline="#1b3862", width=4)
    qr = Image.open(BytesIO(make_qr_png(code, public_url))).resize((290, 290))
    image.paste(qr, (35, 35))
    bold = _font(39, True)
    medium = _font(29, True)
    regular = _font(24)
    draw.text((346, 45), "FIND DOC SCHOOL", font=bold, fill="#1b3862")
    draw.text((346, 115), code, font=medium, fill="#0d7d79")
    draw.text((346, 168), _clip(title, 29), font=regular, fill="#172b4d")
    draw.text((346, 211), _clip(place, 31), font=regular, fill="#172b4d")
    draw.text((346, 292), "Identificação para uso autorizado", font=_font(19), fill="#58687c")
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def _font(size: int, bold: bool = False):
    candidates = (
        ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"]
        if bold else ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"]
    )
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _clip(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[:max_chars - 1] + "…"
