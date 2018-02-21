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


def test_SlashCommandRequest_parses_params(handler):
    # Given: A set of parameters sent from Slack slash command
    body = {
        "command": "/command",
        "text": "some text",
        "token": "some token",
        "user_id": "some user",
        "channel_id": "some_id",
        "channel_name": "rage_cage"
    }

    # When: A query string of those params is parsed
    request = handler.SlashCommandRequest({"body": urlencode(body)}, [])

    # Then: The params are stored as properties
    assert request.command == body["command"]
    assert request.text == body["text"]
    assert request.token == body["token"]
    assert request.user == body["user_id"]
    assert request.channel_id == body["channel_id"]


def test_SlashCommandRequest_parses_actions(handler, mocker):
    # Given: A set of parameters sent from Slack slash command
    body = {
        "command": "/command",
        "text": "action body",
        "token": "some token",
        "user_id": "some user",
        "channel_id": "some_id",
        "channel_name": "rage_cage"
    }

    # When: A query string of those params is parsed
    request = handler.SlashCommandRequest({"body": urlencode(body)}, ["action"])

    # Then: The params are stored as properties
    assert request.text == "action body"
    assert request.action_phrase == "action"
    assert request.action_body == "body"


def test_SlashCommandRequest_handles_no_text(handler, mocker):
    # Given: A set of parameters sent from Slack slash command
    body = {
        "command": "/command",
        "token": "some token",
        "user_id": "some user",
        "channel_id": "some_id",
        "channel_name": "rage_cage"
    }

    # When: A query string of those params is parsed
    print(urlencode(body))
    request = handler.SlashCommandRequest({"body": urlencode(body)}, ["action"])

    # Then: The params are stored as properties
    assert request.text == ""
    assert request.action_phrase is None
    assert request.action_body is None
