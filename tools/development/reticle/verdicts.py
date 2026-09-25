"""Reticle receipt acceptance for the synthetic network controls."""


def network_controls_passed(positive: dict, negative: dict, observation: dict) -> bool:
    positive_verdict = positive.get("verdict")
    negative_verdict = negative.get("verdict")
    calls = observation.get("calls")
    if not isinstance(positive_verdict, dict) or not isinstance(negative_verdict, dict) or not isinstance(calls, list):
        return False
    if not (
        positive.get("verified") == "yes"
        and positive.get("verifiedReason") == "proved"
        and positive_verdict.get("pass") is True
        and negative.get("verified") == "no"
        and negative.get("verifiedReason") == "assertion_failed"
        and negative_verdict.get("pass") is False
        and negative_verdict.get("assertion") == "net.present"
    ):
        return False
    # Exact relative URLs are emitted by this pinned synthetic fixture.
    def captured(url: str, status: int) -> bool:
        return any(isinstance(call, dict) and call.get("method") == "POST"
                   and call.get("url") == url and call.get("status") == status for call in calls)
    return captured("/api/ok", 200) and captured("/api/save", 500)
