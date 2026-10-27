"""Derive a store's brand colour from its uploaded logo.

Shopping-list feedback 2026-08-26: *"for the 'where you'll spend it' colours
for the stores, possible to derive this from the logo uploaded? Would need to
be based on the majority/primary colour. E.g. Woolworths is majority green,
Coles is majority red."*

The derived hex lands on `Store.brand_colour` **at write time** — this runs
once per logo upload, not once per render. That keeps it a server-owned
derived fact (R-003) rather than a computation every client repeats, and it
means the shopping list's store card can colour its segments straight from
the payload it already fetches.

Why the pixel-picking is fussier than "most common colour": a retail logo is
overwhelmingly *background*. Woolworths' mark on a white PNG is ~90% white
pixels, so a naive mode returns white for every logo in existence. The filter
below throws away the two things that are never a brand colour — transparency
and unsaturated pixels (white / black / grey) — and takes the mode of what's
left. A genuinely greyscale logo has no brand colour to find, so it returns
None and the SPA keeps its deterministic hash swatch.
"""
import logging
from collections import Counter
from dora_api.infrastructure.data_url import decode_data_url

_LOGGER = logging.getLogger(__name__)

# Same data-URL convention as every other image on the app
# (C-cross §2.8): `data:image/...;base64,...` stored as UTF-8 bytes.

# Sampling grid. 64x64 is ~4k pixels — enough for a stable mode on a logo,
# small enough that the whole extraction is sub-millisecond.
_SAMPLE_SIZE = 64
# Below this alpha a pixel is background showing through, not ink.
_MIN_ALPHA = 128
# Saturation and value floors, both 0-255 on the HSV conversion. Together
# they reject white, black, and every grey between them — the three colours
# a logo's canvas is actually made of.
_MIN_SATURATION = 60
_MIN_VALUE = 40
# Bucket width for the mode. Anti-aliasing and JPEG artefacts smear a flat
# brand colour across dozens of near-identical RGB triples; quantising to
# 32-step buckets collapses them back into one candidate before counting.
_BUCKET = 32


def dominant_colour(image_blob: bytes | None) -> str | None:
    """Returns the logo's majority brand colour as `#rrggbb`, or None when
    there isn't one (no image, undecodable, or a greyscale-only logo).

    Never raises: a store with an unreadable logo still saves, it just keeps
    the hash-swatch fallback.
    """
    raw = _decode(image_blob)
    if raw is None:
        return None
    try:
        # Imported lazily, exactly like `features/data/barcodes.py`. Pillow
        # arrives via `qrcode[pil]`; an install without it degrades to the
        # hash swatch rather than failing the upload.
        import io

        from PIL import Image

        with Image.open(io.BytesIO(raw)) as source:
            image = source.convert("RGBA")
            image.thumbnail((_SAMPLE_SIZE, _SAMPLE_SIZE))
            # Raw RGBA bytes rather than `getdata()`, which Pillow has
            # deprecated. Four bytes per pixel, in order.
            pixels = image.tobytes()
    except Exception:
        _LOGGER.info(
            "Could not read store logo for colour extraction; "
            "falling back to the hash swatch.",
            exc_info=True,
        )
        return None

    counts: Counter[tuple[int, int, int]] = Counter()
    totals: dict[tuple[int, int, int], list[int]] = {}
    for offset in range(0, len(pixels), 4):
        red, green, blue, alpha = pixels[offset:offset + 4]
        if alpha < _MIN_ALPHA:
            continue
        if not _is_chromatic(red, green, blue):
            continue
        bucket = (red // _BUCKET, green // _BUCKET, blue // _BUCKET)
        counts[bucket] += 1
        running = totals.setdefault(bucket, [0, 0, 0])
        running[0] += red
        running[1] += green
        running[2] += blue

    if not counts:
        return None

    bucket, size = counts.most_common(1)[0]
    # Average the bucket's real pixels rather than returning the bucket's
    # centre — a 32-step centre can sit visibly off the brand's actual hue.
    running = totals[bucket]
    return "#{:02x}{:02x}{:02x}".format(
        running[0] // size, running[1] // size, running[2] // size
    )


def _is_chromatic(red: int, green: int, blue: int) -> bool:
    """True when a pixel carries actual hue — i.e. it isn't part of the
    white / black / grey canvas the mark sits on."""
    high = max(red, green, blue)
    low = min(red, green, blue)
    if high < _MIN_VALUE:
        return False
    saturation = 0 if high == 0 else ((high - low) * 255) // high
    return saturation >= _MIN_SATURATION


def _decode(image_blob: bytes | None) -> bytes | None:
    decoded = decode_data_url(image_blob)
    return decoded[1] if decoded else None
