"""Post one part of the wizard's draft to `/onboarding/finish` (14-D2) and read
that part's result back, so the seed tests keep their per-step assertions."""
import requests

FINISH = "http://localhost:5170/api/onboarding/finish"


class FinishPart:
    def __init__(self, response: requests.Response, key: str) -> None:
        self.response = response
        self.status_code = response.status_code
        self.text = response.text
        self._key = key

    def json(self):
        return self.response.json()[self._key]


def finish_seed(body: dict) -> FinishPart:
    return FinishPart(requests.post(FINISH, json={"seed": body}), "seed")


def finish_items(body: dict) -> FinishPart:
    return FinishPart(requests.post(FINISH, json={"items": body}), "items")


def finish_demo() -> FinishPart:
    return FinishPart(requests.post(FINISH, json={"seed_demo": True}), "demo")
