import pytest
import requests

from halo.gateway import AuthError, ForbiddenError, GatewayError, HaloGateway
from halo.operations import ALL_ASSESSMENT_GRADES, GET_ALL_CLASSES, UPCOMING_ASSIGNMENTS


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text_body=None):
        self.status_code = status_code
        self._payload = payload
        self._text_body = text_body

    def json(self):
        if self._text_body is not None:
            raise ValueError("not json")
        return self._payload


class FakeHTTP:
    """Stands in for requests.Session, capturing the outbound call."""

    def __init__(self, response=None, raises=None):
        self.response = response
        self.raises = raises
        self.calls = []

    def post(self, url, json=None, headers=None, timeout=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self.raises:
            raise self.raises
        return self.response

    def close(self):
        pass


def make_gateway(http):
    gw = HaloGateway("https://gateway.example/", "https://halo.example/")
    gw._http = http
    return gw


def test_successful_call_returns_data():
    http = FakeHTTP(FakeResponse(200, {"data": {"getAllClasses": []}}))
    gw = make_gateway(http)
    data = gw.execute("auth-tok", "ctx-tok", GET_ALL_CLASSES)
    assert data == {"getAllClasses": []}


def test_sends_documented_auth_headers():
    http = FakeHTTP(FakeResponse(200, {"data": {}}))
    gw = make_gateway(http)
    gw.execute("auth-tok", "ctx-tok", GET_ALL_CLASSES)

    headers = http.calls[0]["headers"]
    assert headers["Authorization"] == "Bearer auth-tok"
    assert headers["Contexttoken"] == "Bearer ctx-tok"
    assert headers["Gql-Operation-Name"] == "GetAllClasses"


def test_operation_name_matches_body_and_header():
    http = FakeHTTP(FakeResponse(200, {"data": {}}))
    gw = make_gateway(http)
    gw.execute("a", "b", GET_ALL_CLASSES)
    call = http.calls[0]
    assert call["json"]["operationName"] == call["headers"]["Gql-Operation-Name"]


def test_course_context_headers_only_when_operation_declares_them():
    http = FakeHTTP(FakeResponse(200, {"data": {}}))
    gw = make_gateway(http)

    gw.execute("a", "b", GET_ALL_CLASSES)
    assert "Current-Class-Slug-Id" not in http.calls[0]["headers"]

    gw.execute("a", "b", UPCOMING_ASSIGNMENTS, {"slugId": "s"}, slug_id="s", course_class_id="c")
    headers = http.calls[1]["headers"]
    assert headers["Current-Class-Slug-Id"] == "s"
    assert headers["Current-Course-Class-Id"] == "c"


def test_slug_only_operation_omits_course_class_header():
    http = FakeHTTP(FakeResponse(200, {"data": {}}))
    gw = make_gateway(http)
    gw.execute("a", "b", ALL_ASSESSMENT_GRADES, {"courseClassSlugId": "s"}, slug_id="s")
    headers = http.calls[0]["headers"]
    assert headers["Current-Class-Slug-Id"] == "s"
    assert "Current-Course-Class-Id" not in headers


def test_missing_course_context_sent_as_empty_string():
    # Mirrors the live Halo app, which sends these headers empty rather than absent.
    http = FakeHTTP(FakeResponse(200, {"data": {}}))
    gw = make_gateway(http)
    gw.execute("a", "b", UPCOMING_ASSIGNMENTS, {"slugId": "s"})
    headers = http.calls[0]["headers"]
    assert headers["Current-Class-Slug-Id"] == ""
    assert headers["Current-Course-Class-Id"] == ""


@pytest.mark.parametrize("status", [401, 403])
def test_rejected_tokens_raise_auth_error(status):
    gw = make_gateway(FakeHTTP(FakeResponse(status, {})))
    with pytest.raises(AuthError):
        gw.execute("a", "b", GET_ALL_CLASSES)


def test_server_error_raises_gateway_error():
    gw = make_gateway(FakeHTTP(FakeResponse(500, {})))
    with pytest.raises(GatewayError) as exc:
        gw.execute("a", "b", GET_ALL_CLASSES)
    assert "500" in str(exc.value)


def test_graphql_errors_fail_even_with_partial_data():
    # A 2xx response can still carry an errors array; treat it as a failure.
    payload = {"data": {"getAllClasses": []}, "errors": [{"message": "boom", "path": ["x"]}]}
    gw = make_gateway(FakeHTTP(FakeResponse(200, payload)))
    with pytest.raises(GatewayError) as exc:
        gw.execute("a", "b", GET_ALL_CLASSES)
    assert "boom" in str(exc.value)


def test_permission_evaluator_is_forbidden_not_auth():
    # Observed with a valid session and a slugId the account is not enrolled in.
    # Misclassifying this as an auth failure would churn the session on every
    # request for an inaccessible course.
    payload = {
        "errors": [{"message": "Permission Evaluator exception on Class : ...Impl"}]
    }
    gw = make_gateway(FakeHTTP(FakeResponse(200, payload)))
    with pytest.raises(ForbiddenError):
        gw.execute("a", "b", GET_ALL_CLASSES)


def test_forbidden_error_is_not_an_auth_error():
    payload = {"errors": [{"message": "Permission Evaluator exception"}]}
    gw = make_gateway(FakeHTTP(FakeResponse(200, payload)))
    with pytest.raises(GatewayError) as exc:
        gw.execute("a", "b", GET_ALL_CLASSES)
    assert not isinstance(exc.value, AuthError)


def test_expired_token_message_classified_as_auth():
    payload = {"errors": [{"message": "JWT expired at 2026-01-01"}]}
    gw = make_gateway(FakeHTTP(FakeResponse(200, payload)))
    with pytest.raises(AuthError):
        gw.execute("a", "b", GET_ALL_CLASSES)


def test_unrecognised_error_does_not_trigger_renewal():
    # Anything unfamiliar must stay a plain GatewayError so it cannot cause
    # the session to be re-minted.
    payload = {"errors": [{"message": "something we have never seen"}]}
    gw = make_gateway(FakeHTTP(FakeResponse(200, payload)))
    with pytest.raises(GatewayError) as exc:
        gw.execute("a", "b", GET_ALL_CLASSES)
    assert not isinstance(exc.value, (AuthError, ForbiddenError))


def test_transport_failure_raises_gateway_error():
    gw = make_gateway(FakeHTTP(raises=requests.ConnectionError("no route")))
    with pytest.raises(GatewayError) as exc:
        gw.execute("a", "b", GET_ALL_CLASSES)
    assert "transport failure" in str(exc.value)


def test_non_json_body_raises_gateway_error():
    gw = make_gateway(FakeHTTP(FakeResponse(200, text_body="<html>")))
    with pytest.raises(GatewayError):
        gw.execute("a", "b", GET_ALL_CLASSES)


def test_missing_data_key_raises_gateway_error():
    gw = make_gateway(FakeHTTP(FakeResponse(200, {"extensions": {}})))
    with pytest.raises(GatewayError):
        gw.execute("a", "b", GET_ALL_CLASSES)
