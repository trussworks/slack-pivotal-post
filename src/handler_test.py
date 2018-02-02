import json
import os
import pytest
from urllib.parse import urlencode


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


def test_response_returns_statuscode_and_message(handler):
    # Given: A status code
    CODE = 200
    MESSAGE = "message"
    # When: The response method is called
    response = handler.response(CODE, MESSAGE)
    parsed_body = json.loads(response["body"])
    # Then: A dict is returned with the right statusCode
    assert response["statusCode"] == str(CODE)
    assert parsed_body["text"] == MESSAGE


def test_SlackRequest_parses_params(handler):
    # Given: A set of parameters sent from Slack webhook
    body = {
        "trigger_word": "trigger word",
        "text": "some text",
        "token": "some token",
        "user_name": "some user",
        "channel_name": "rage_cage",
    }

    # When: A query string of those params is parsed
    request = handler.SlackRequest({"body": urlencode(body)})

    # Then: The params are stored as properties
    assert request.command == body["trigger_word"]
    assert request.text == body["text"]
    assert request.token == body["token"]
    assert request.user == body["user_name"]
    assert request.channel == body["channel_name"]
