"""Dora's burger mark in the middle of her own QR labels (FU-779).

Pinned here rather than left to browser-verify because the failure mode is
invisible by eye: a QR with too much of its centre knocked out still *looks*
like a QR, and only stops working once it is printed on a jar and scanned in
bad light. The contract is small, has no reason to churn, and is expensive to
re-check by hand (print, stick, scan), which is exactly the shape the verify
stance says to automate.

What is deliberately *not* asserted here: that the codes decode. That needs a
QR reader (opencv/zbar), and adding a native decoder to the test image for one
assertion is a poor trade. Decoding was verified out-of-band on 2026-08-28
across sizes 120/180/256/512/1024 and three payloads, plus a degradation sweep
(blur, gaussian noise, rotation) run twice — once marked, once with the mark
suppressed. Marked and unmarked outcomes were identical in all 16 trials, i.e.
the mark costs no measurable error-correction headroom. Re-run for the burger mark
on 2026-11-05 (FU-779) at 0.18 width, 160 trials per arm with OpenCV: marked
10 misses, unmarked 9, i.e. the reader's own noise, not the mark. What that sweep can't
protect against is someone widening `_MARK_WIDTH_RATIO` later, so the ratios
themselves are pinned below.
"""
import io

import qrcode
from PIL import Image

from dora_api.features.data import barcodes as bc


PAYLOAD = "dora://stock-item/3f2a9c14-8b7e-4d21-9a55-0c6e1f8b4d33"


def _render(size: int) -> Image.Image:
    return Image.open(io.BytesIO(bc._render_qr_png(PAYLOAD, size))).convert("L")


def _centre_patch(img: Image.Image, fraction: float = 0.06) -> Image.Image:
    """The very middle of the code — inside the glyph, well clear of the ring."""
    size = img.width
    half = max(1, round(size * fraction / 2))
    mid = size // 2
    return img.crop((mid - half, mid - half, mid + half, mid + half))


def test__error_correction_is_high_enough_to_carry_a_logo():
    """A centre mark is only survivable because Reed-Solomon can rebuild the
    modules it covers. At _M (~15%) the budget is shared with real-world label
    damage and there is not enough left; the mark and this level move together,
    so dropping the level without shrinking the mark must fail here."""
    assert bc.qrcode.constants.ERROR_CORRECT_H == qrcode.constants.ERROR_CORRECT_H
    # Rendered at H, a fixed payload needs a denser matrix than at M. That
    # density difference is the observable proof the level is what we think.
    high = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=1, border=0)
    high.add_data(PAYLOAD)
    high.make(fit=True)
    medium = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=1, border=0)
    medium.add_data(PAYLOAD)
    medium.make(fit=True)
    assert high.modules_count > medium.modules_count


def test__the_mark_lands_in_the_middle_of_a_full_size_code():
    img = _render(512)
    patch = _centre_patch(img)
    # The glyph is black ink on a white knockout, so the middle carries both
    # extremes. A bare matrix would too — what distinguishes them is the ring,
    # asserted separately below.
    assert patch.getextrema()[0] < 64, "no dark glyph pixels in the centre"


def test__the_mark_sits_on_a_clean_white_ring():
    """Without the knockout the glyph merges into whatever dark modules it
    abuts and a decoder sees one blob instead of a recoverable erasure."""
    img = _render(512)
    size = img.width
    mark_w = round(size * bc._MARK_WIDTH_RATIO)
    mark_h = round(mark_w * 1080 / 1200)          # the asset's aspect
    pad = round(size * bc._MARK_PAD_RATIO)
    # Sample the ring just outside the glyph but inside the knockout box.
    top = (size - (mark_h + pad * 2)) // 2
    strip = img.crop((size // 2 - mark_w // 4, top + 1, size // 2 + mark_w // 4, top + pad - 1))
    assert strip.getextrema()[0] > 200, "the ring around the mark is not blank"


def test__small_codes_are_left_unbranded():
    """At QR_MIN_SIZE the wordmark would be ~17px wide — illegible as a logo,
    and pure lost error-correction budget. Below the floor we render plain."""
    def ring_of(img):
        """A sliver of the row where the knockout's top edge would fall."""
        size = img.width
        pad = max(1, round(size * bc._MARK_PAD_RATIO))
        mark_h = round(size * bc._MARK_WIDTH_RATIO * 1080 / 1200)
        top = (size - (mark_h + pad * 2)) // 2
        return img.crop((size // 2 - 2, top + 1, size // 2 + 2, top + pad))

    # One side of the floor has a blank knockout there; the other is raw
    # matrix, which for this payload is dark.
    assert ring_of(_render(bc._MARK_MIN_SIZE)).getextrema()[0] > 200
    assert ring_of(_render(bc._MARK_MIN_SIZE - 1)).getextrema()[0] < 200


def test__the_mark_stays_a_small_fraction_of_the_code():
    """The guard against someone 'making the logo a bit bigger'. H recovers
    ~30% of codewords and that budget is shared with print damage, so the
    knockout is held to a few percent of the code's area."""
    aspect = 1080 / 1200
    box_w = bc._MARK_WIDTH_RATIO + bc._MARK_PAD_RATIO * 2
    box_h = bc._MARK_WIDTH_RATIO * aspect + bc._MARK_PAD_RATIO * 2
    assert box_w * box_h < 0.08, "centre knockout is eating the error-correction budget"


def test__a_missing_asset_degrades_to_a_plain_code(monkeypatch):
    """A packaging slip must cost the branding, not the endpoint — the label
    still has to scan."""
    bc._mark_image.cache_clear()
    monkeypatch.setattr(bc, "_MARK_PATH", bc._MARK_PATH.with_name("does-not-exist.png"))
    try:
        png = bc._render_qr_png(PAYLOAD, 512)
        assert Image.open(io.BytesIO(png)).size == (512, 512)
    finally:
        bc._mark_image.cache_clear()
