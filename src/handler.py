import json
import html
import logging
import os
import re
from urllib.parse import parse_qs

import boto3
import requests

deployed_slack_token = os.environ["slack_token"]
pivotal_token = os.environ["pivotal_token"]
sdb_domain = os.environ["sdb_domain"]

pivotal_headers = {
    "X-TrackerToken": pivotal_token,
    "Content-Type": "application/json"
}
pivotal_url = "https://www.pivotaltracker.com/services/v5"
story_post_url = pivotal_url + "/projects/{project_id}/stories"
pivotal_project_pattern = re.compile(r"pivotaltracker\.com/n/projects/([\d]+)")
pivotal_error_codes = ("unauthorized_operation", "unfound_resource")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# These are commands that trigger special actions
PAIR_PHRASE = "pair"
UNPAIR_PHRASE = "unpair"
HELP_PHRASE = "help"

KNOWN_PHRASES = (
    PAIR_PHRASE,
    UNPAIR_PHRASE,
    HELP_PHRASE)

TUTORIAL_RESPONSE = (
    "Specify a story name. Optional: add a description after a semicolon.\n"
    "e.g. `{command} Buy more ethernet cables; We are running out`\n")

MISSING_PAIR_RESPONSE = (
    "Pivotal integration hasn't been set up in this channel yet.\n"
    "Invite the user tied to this bot's API key to your project and\n"
    "pair it with `{command} pair <Pivotal project URL>`\n")

MISSING_PROJECT_ACCESS_RESPONSE = (
    "It looks like slack-pivotal-tracker-bot doesn't have access to this Pivotal project yet.\n"
    "Invite the user tied to this bot's API key to your Pivotal project and try pairing again.\n")

SUCCESSFUL_PAIR_RESPONSE = (
    "Success! You've paired *#{channel}* with *{project_name}*.\n"
    "For more info about how to post a story type `{command} help`\n"
    "Unpair this channel from *{project_name}* with `{command} unpair`\n")

SUCCESSFUL_UNPAIR_RESPONSE = (
    "Successfully removed pairing between *#{channel}* and *{project_name}*.\n")

SUCCESSFUL_POST_RESPONSE = (
    "Story *{story}* added to *{project}*.\n"
    "{url}\n")


class Error(Exception):
    pass


class ChannelPairingException(Error):
    """Exception when channel pairing fails."""
    pass


class PivotalProjectAccessException(Error):
    """Exception when attempt to query Pivotal project fails."""
    pass


def response(code, message):
    """Returns a response dictionary."""
    return {
        "statusCode": str(code),
        "body": json.dumps({
            "text": message,
            "response_type": "in_channel",
            "user_name": "PivotalTracker"
        }),
        "headers": {
            "Content-Type": "application/json",
        },
    }


def get_sdb_client():
    return boto3.client("sdb")


class SlackRequest():
    """Class that encapsulates an incoming Slack request.

    Attributes:
        command: A string representing the command key word. (e.g. "!pivotal")
        text: The raw text contents of the incoming message.
        token: Slack API token of the incoming message.
        user: Username of user who posted the Slack message.
        channel: Name of Slack channel where message was posted in.
        parsed_msg: Raw message test minus command word.
        project_id: ID of Pivotal project that Slack channel is bound to.
        action_phrase: Key command phrase used to instruct what action to take.
        action_body: Remaining action body if action phrase is detected
    """

    def __init__(self, event):
        params = parse_qs(event["body"])
        logger.info(params)
        self.command = params["trigger_word"][0]
        self.text = params["text"][0]
        self.token = params["token"][0]
        self.user = params["user_name"][0]
        self.channel = params["channel_name"][0]

        # Incoming message will always be prepended with command word, so
        # strip it out and parse escaped characters
        msg_contents = self.text.replace(self.command, "", 1)
        self.parsed_msg = html.unescape(msg_contents).strip()

        # "Action phrase" is assumed to be the first word provided
        msg_words = self.parsed_msg.split()
        action_phrase = msg_words[0]
        if action_phrase in KNOWN_PHRASES:
            self.action_phrase = action_phrase
            self.action_body = " ".join(msg_words[1:])
        else:
            self.action_phrase = None
            self.action_body = None


def get_channel_pairing(channel):
    """Retrieves Piotal Tracker project ID from SDB, or returns None"""
    sdb_client = get_sdb_client()
    project_attr = sdb_client.get_attributes(
        DomainName=sdb_domain,
        ItemName=channel,
        AttributeNames=["project_id"],
        ConsistentRead=True).get("Attributes")
    if project_attr:
        logger.info(project_attr)
        return project_attr[0]["Value"]
    else:
        return None


def get_project_name(project_id):
        """Returns a JSON response object describing a Pivotal project"""
        logger.info("Querying Pivotal project info")
        project_info = requests.get(pivotal_url + "/projects/" + project_id,
                                    headers=pivotal_headers).json()

        if project_info.get("code") in pivotal_error_codes:
            raise PivotalProjectAccessException()
        else:
            return project_info["name"]


def pair_channel(channel, action_body):
    # Attempts to pair a channel to a given Pivotal Tracker project
    logger.info(
        "Attempting to pair channel {} to a Tracker project".format(channel))
    valid_project_url = pivotal_project_pattern.search(action_body)

    if valid_project_url:
        # Extract Tracker project ID
        return pivotal_project_pattern.search(action_body)[1]
    else:
        raise ChannelPairingException()


def store_pairing(channel, project_id):
    """Stores pairing as attribute on SDB."""
    logger.info("Storing pairing between {} and {}".format(
        channel, project_id))
    sdb_client = get_sdb_client()
    sdb_client.put_attributes(
        DomainName=sdb_domain,
        ItemName=channel,
        Attributes=[{
            "Name": "project_id",
            "Value": project_id,
            "Replace": True,
        }])


def remove_pairing(channel, project_name):
    """Deletes pairing from SDB."""
    logger.info("Removing pairing between {} and {}".format(
        channel, project_name))
    sdb_client = get_sdb_client()
    sdb_client.delete_attributes(
        DomainName=sdb_domain,
        ItemName=channel)


def post_new_tracker_story(message, project_id, user):
    """Posts message contents as a story to the bound project."""
    if ";" in message:
        name, description = message.split(";", maxsplit=1)
    else:
        name, description = (message, "")
    story_name = "{name} (from {user})".format(
        name=name.strip(), user=user)
    response = requests.post(
        story_post_url.format(project_id=project_id),
        headers=pivotal_headers,
        json={"name": story_name,
              "description": description.strip()})
    story_url = response.json()["url"]
    return name, story_url


def lambda_handler(event, context):
    """Entrypoint for Lambda function. Contains core logic."""
    # TODO(Patrick): break up this function
    parsed_request = SlackRequest(event)
    paired_tracker_project = get_channel_pairing(parsed_request.channel)

    # Just a basic sanity check that we're talking to the Slack app we want to
    if parsed_request.token != deployed_slack_token:
        logger.error(
            "Request token ({}) does not match expected".format(parsed_request.token))
        return response(400, "Invalid request token")

    # If there's no paired project, we're either pairing one to the channel or
    # we should return a helpful message
    if paired_tracker_project is None:
        if parsed_request.action_phrase == PAIR_PHRASE:
            try:
                project_id = pair_channel(parsed_request.channel,
                                          parsed_request.action_body)
                store_pairing(parsed_request.channel, project_id)
                project_name = get_project_name(project_id)
                return response(200, SUCCESSFUL_PAIR_RESPONSE.format(
                    project_name=project_name,
                    channel=parsed_request.channel,
                    command=parsed_request.command))
            except PivotalProjectAccessException:
                # Found a pair request, but missing access to project
                return response(200, MISSING_PROJECT_ACCESS_RESPONSE)
            except ChannelPairingException:
                # Invalid pair request, show generic pairing tutorial
                return response(200, MISSING_PAIR_RESPONSE.format(
                    command=parsed_request.command))
        else:
            # No pair request found, show generic pairing tutorial
            return response(200, MISSING_PAIR_RESPONSE.format(
                command=parsed_request.command))

    # Either there's no text or user asked for help, so provide help
    if len(parsed_request.parsed_msg) == 0 or parsed_request.action_phrase == HELP_PHRASE:
        return response(
            200, TUTORIAL_RESPONSE.format(command=parsed_request.command))

    # User wants to unpair their current channel from a Tracker project
    if parsed_request.action_phrase == UNPAIR_PHRASE:
        project_name = get_project_name(paired_tracker_project)
        remove_pairing(parsed_request.channel, project_name)
        return response(200, SUCCESSFUL_UNPAIR_RESPONSE.format(
            project_name=project_name,
            channel=parsed_request.channel))

    # If no other actions were taken then we're posting a new Tracker story
    project_name = get_project_name(paired_tracker_project)
    story_name, story_url = post_new_tracker_story(
        parsed_request.parsed_msg, paired_tracker_project, parsed_request.user)
    return response(200, SUCCESSFUL_POST_RESPONSE.format(
        story=story_name,
        project=project_name,
        url=story_url))
