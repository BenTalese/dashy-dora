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
# Decompression-bomb guard. A tiny, highly-compressible PNG can *declare*
# e.g. 13k x 13k pixels and expand to ~700 MB once decoded — enough to OOM
# the single API worker, and any member can trigger it on store create/
# update. `Image.open` only reads the header, so the declared size is
# checked against this cap BEFORE anything is decoded; an oversized logo
# just skips colour extraction (the store still saves, hash swatch shown).
# No real logo comes near 4096 px on a side.
_MAX_LOGO_DIMENSION = 4096
# Process-wide Pillow ceiling (defence in depth for any decode path). Pillow
# warns above this and raises DecompressionBombError above 2x. Its default
# (~89 MP → error at ~179 MP) lets a 13k x 13k bomb through; 64 MP still
# admits a 48 MP phone photo elsewhere in the app (recipe step images).
_PILLOW_MAX_IMAGE_PIXELS = 64_000_000


def _cap_pillow_canvas(Image) -> None:
    """Lower Pillow's process-wide decompression-bomb ceiling once. Stated
    here (the only module that decodes an untrusted image before sizing it)
    and applied idempotently, so behaviour doesn't depend on whether a logo
    has been processed since boot."""
    if Image.MAX_IMAGE_PIXELS is None or Image.MAX_IMAGE_PIXELS > _PILLOW_MAX_IMAGE_PIXELS:
        Image.MAX_IMAGE_PIXELS = _PILLOW_MAX_IMAGE_PIXELS


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

        _cap_pillow_canvas(Image)

        with Image.open(io.BytesIO(raw)) as source:
            # Header-only at this point — refuse oversized canvases before
            # the pixel data is decoded.
            width, height = source.size
            if width > _MAX_LOGO_DIMENSION or height > _MAX_LOGO_DIMENSION:
                _LOGGER.info(
                    "Store logo is %sx%s (cap %s); skipping colour extraction.",
                    width, height, _MAX_LOGO_DIMENSION,
                )
                return None
            # Shrink BEFORE the mode conversion so `convert` only ever
            # touches a <=64x64 image. `draft` lets JPEG decode at reduced
            # scale (no-op for other formats).
            source.draft("RGB", (_SAMPLE_SIZE, _SAMPLE_SIZE))
            source.thumbnail((_SAMPLE_SIZE, _SAMPLE_SIZE))
            image = source.convert("RGBA")
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
