import os
import pytest


ENV_VAR_MOCK = {
    "slack_token": "something",
    "pivotal_token": "something",
    "sdb_domain": "something",
}


@pytest.fixture
def handler(mocker):
    mocker.patch.object(os, "environ", return_value=ENV_VAR_MOCK)
    import handler
    return handler


def test_response_returns_statuscode(handler):
    # Given: A status code
    CODE = 200
    MESSAGE = "message"
    # When: The response method is called
    response = handler.response(CODE, MESSAGE)
    # Then: A dict is returned with the right statusCode
    assert response["statusCode"] == str(CODE)
