"""FU-334 — receipt-photo attachments on shopping lists.

End-to-end coverage of the add/list/bytes/delete cycle, the draft-list
lifecycle gate, and cascade behaviour on list delete. Mirrors the
recipe step-image pattern: data-URL in, raw bytes out via a dedicated
endpoint, metadata-only on the detail payload.
"""
import base64
from uuid import uuid4

import requests

SHOPPING_LISTS = "http://localhost:5170/api/shopping-lists"

# 1×1 transparent PNG, as a `data:image/...;base64,...` string.
_PNG_BYTES = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d4944415478da6364f80f00000100010055f6caab0000000049454e44ae426082"
)
PNG_DATA_URL = f"data:image/png;base64,{base64.b64encode(_PNG_BYTES).decode()}"


def _create_list(name: str) -> str:
    resp = requests.post(SHOPPING_LISTS, json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["shopping_list_id"]


def _detail(list_id: str) -> dict:
    resp = requests.get(f"{SHOPPING_LISTS}/{list_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()


def _add_attachment(list_id: str, data_url: str = PNG_DATA_URL):
    return requests.post(
        f"{SHOPPING_LISTS}/{list_id}/attachments",
        json={"image_data_url": data_url},
    )


def test__detail_payload__exposes_empty_attachments_array_for_shopping_list(api):
    list_id = _create_list(f"FU-334 empty attachments {uuid4()}")
    detail = _detail(list_id)
    assert detail.get("attachments") == []


def test__attach_to_shopping_list__appears_in_detail__bytes_round_trip(api):
    list_id = _create_list(f"FU-334 attach happy {uuid4()}")

    resp = _add_attachment(list_id)
    assert resp.status_code == 200, resp.text
    attachment_id = resp.json()["attachment_id"]

    detail = _detail(list_id)
    attachments = detail["attachments"]
    assert len(attachments) == 1
    assert attachments[0]["attachment_id"] == attachment_id
    assert attachments[0]["sequence"] == 0

    bytes_resp = requests.get(
        f"{SHOPPING_LISTS}/{list_id}/attachments/{attachment_id}"
    )
    assert bytes_resp.status_code == 200
    assert bytes_resp.headers["Content-Type"].startswith("image/")
    assert bytes_resp.content == _PNG_BYTES


def test__attach_to_a_list_with_nothing_ticked__is_allowed(api):
    # UX v5: no draft state left to refuse; any active list takes a photo.
    list_id = _create_list(f"FU-334 any list {uuid4()}")
    resp = _add_attachment(list_id)
    assert resp.status_code == 200, resp.text
    assert len(_detail(list_id)["attachments"]) == 1


def test__attach__rejects_non_data_url(api):
    list_id = _create_list(f"FU-334 bad payload {uuid4()}")
    resp = _add_attachment(list_id, "not a data url")
    assert resp.status_code in (400, 409, 422), resp.text


def test__multiple_attachments__retain_sequence_order(api):
    list_id = _create_list(f"FU-334 multi {uuid4()}")
    ids = []
    for _ in range(3):
        resp = _add_attachment(list_id)
        assert resp.status_code == 200, resp.text
        ids.append(resp.json()["attachment_id"])

    detail_attachments = _detail(list_id)["attachments"]
    assert [a["attachment_id"] for a in detail_attachments] == ids
    assert [a["sequence"] for a in detail_attachments] == [0, 1, 2]


def test__delete_attachment__removes_it_from_detail(api):
    list_id = _create_list(f"FU-334 delete {uuid4()}")
    attachment_id = _add_attachment(list_id).json()["attachment_id"]

    del_resp = requests.delete(
        f"{SHOPPING_LISTS}/{list_id}/attachments/{attachment_id}"
    )
    assert del_resp.status_code == 204, del_resp.text
    assert _detail(list_id)["attachments"] == []

    # Bytes endpoint now 404s.
    bytes_resp = requests.get(
        f"{SHOPPING_LISTS}/{list_id}/attachments/{attachment_id}"
    )
    assert bytes_resp.status_code == 404


def test__delete_list__cascades_to_attachments(api):
    list_id = _create_list(f"FU-334 cascade {uuid4()}")
    attachment_id = _add_attachment(list_id).json()["attachment_id"]

    assert requests.delete(f"{SHOPPING_LISTS}/{list_id}").status_code == 204

    # Both the list and its attachment are gone.
    assert requests.get(f"{SHOPPING_LISTS}/{list_id}").status_code == 404
    bytes_resp = requests.get(
        f"{SHOPPING_LISTS}/{list_id}/attachments/{attachment_id}"
    )
    assert bytes_resp.status_code == 404


def test__attachments_survive_finish__on_done_list(api):
    """A finished list keeps its receipts — the whole point is record-keeping."""
    list_id = _create_list(f"FU-334 finish {uuid4()}")
    attachment_id = _add_attachment(list_id).json()["attachment_id"]

    finish_resp = requests.post(f"{SHOPPING_LISTS}/{list_id}/finish")
    assert finish_resp.status_code == 200, finish_resp.text

    detail = _detail(list_id)
    assert detail["status"] == "done"
    attachment_ids = [a["attachment_id"] for a in detail["attachments"]]
    assert attachment_id in attachment_ids
