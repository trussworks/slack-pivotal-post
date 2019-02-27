import json
import html
import logging
import os
import re
from slackclient import SlackClient
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
project_membership_url = pivotal_url + "/projects/{project_id}/memberships"
pivotal_project_pattern = re.compile(r"pivotaltracker\.com/n/projects/([\d]+)")
pivotal_error_codes = ("unauthorized_operation", "unfound_resource")

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# These are commands that trigger special actions
PAIR_PHRASE = "pair"
UNPAIR_PHRASE = "unpair"
HELP_PHRASE = "help"
EXPORT_PHRASE = "view_pairings"

PRIVATE_CHANNEL_NAME = "privategroup"

KNOWN_PHRASES = (
    PAIR_PHRASE,
    UNPAIR_PHRASE,
    HELP_PHRASE,
    EXPORT_PHRASE)

TUTORIAL_RESPONSE = (
    "Specify a story name. Optional: add a description after a semicolon.\n"
    "e.g. `{command} Buy more ethernet cables; We are running out`\n")

EXPORT_PAIRINGS_RESPONSE = (
    "Here are the currently paired channels:\n"
    "```\n"
    "{pairing_json}\n"
    "```")

MISSING_PAIR_RESPONSE = (
    "Pivotal integration hasn't been set up in this channel yet.\n"
    "Invite the user tied to this bot's API key to your project and\n"
    "pair it with `{command} pair <Pivotal project URL>`\n")

MISSING_PROJECT_ACCESS_RESPONSE = (
    "It looks like slack-pivotal-tracker-bot doesn't have access to this Pivotal project yet.\n"
    "Invite the user tied to this bot's API key to your Pivotal project and try pairing again.\n")

SUCCESSFUL_PAIR_RESPONSE = (
    "Success! You've paired {channel} with *{project_name}*.\n"
    "For more info about how to post a story type `{command} help`\n"
    "Unpair this channel from *{project_name}* with `{command} unpair`\n")

SUCCESSFUL_UNPAIR_RESPONSE = (
    "Successfully removed pairing between {channel} and *{project_name}*.\n")

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


class SlashCommandRequest():
    """Class that encapsulates an Slack Slash Command request.

    Attributes:
        command: A string representing the command key word. (e.g. "/pivotal")
        text: The raw text contents of the incoming message.
        token: Slack API token of the incoming message.
        user: Name of user who posted the Slack message.
        channel_id: Global ID of Slack channel where message was posted in.
        action_phrase: Key command phrase used to instruct what action to take.
        action_body: Remaining action body if action phrase is detected
    """

    def __init__(self, event, known_phrases):
        params = parse_qs(event["body"])
        logger.info(params)
        self.command = params["command"][0]
        self.text = params.get("text", [""])[0]
        self.token = params["token"][0]
        self.user = params["user_name"][0]
        self.user_id = params["user_id"][0]
        self.channel_id = params["channel_id"][0]
        self.channel_name = params["channel_name"][0]

        self.text = html.unescape(self.text).strip()

        # We don't get reverse translation of channel IDs for private groups,
        # so sub in some generic text
        if self.channel_name == PRIVATE_CHANNEL_NAME:
            self.formatted_channel = "this channel"
        else:
            self.formatted_channel = "*<#{}>*".format(self.channel_id)

        # "Action phrase" is assumed to be the first word provided
        msg_words = self.text.split()
        if len(msg_words) and msg_words[0] in known_phrases:
            self.action_phrase = msg_words[0]
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


def get_pivotal_project_id(action_body):
    """Attempts to extract a Pivotal Tracker project ID from a pair command"""
    valid_project_url = pivotal_project_pattern.search(action_body)

    if valid_project_url:
        # Extract Tracker project ID
        return pivotal_project_pattern.search(action_body)[1]
    else:
        raise ChannelPairingException()


def store_pairing(channel_id, project_id):
    """Stores pairing as attribute on SDB."""
    logger.info("Storing pairing between {} and {}".format(
        channel_id, project_id))
    sdb_client = get_sdb_client()
    sdb_client.put_attributes(
        DomainName=sdb_domain,
        ItemName=channel_id,
        Attributes=[{
            "Name": "project_id",
            "Value": project_id,
            "Replace": True,
        }])


def remove_pairing(channel_id, project_name):
    """Deletes pairing from SDB."""
    logger.info("Removing pairing between {} and {}".format(
        channel_id, project_name))
    sdb_client = get_sdb_client()
    sdb_client.delete_attributes(
        DomainName=sdb_domain,
        ItemName=channel_id)


def post_new_tracker_story(message, project_id, user, user_id):
    """Posts message contents as a story to the bound project."""
    if ";" in message:
        name, description = message.split(";", maxsplit=1)
    else:
        name, description = (message, "")

    pivotal_user_id = get_pivotal_user_id(project_id, user, user_id)
    if pivotal_user_id:
        content = {
            "name": name.strip(),
            "description": description.strip(),
            "requested_by_id": pivotal_user_id}
    else:
        story_name = "{name} (from {user})".format(
            name=name.strip(), user=user)
        content = {
            "name": story_name,
            "description": description.strip(),
            "requested_by_id": pivotal_user_id}
    response = requests.post(
        story_post_url.format(project_id=project_id),
        headers=pivotal_headers,
        json=content)
    story_url = response.json()["url"]
    return name, story_url


def get_pivotal_user_id(project_id, user, user_id):
    """Gets pivotal user id for the Slack user"""
    slack_email = get_slack_email(user_id)
    # Get all the members of Pivotal project and finds the
    # Pivotal user id associated with the slack email
    membership_response = requests.get(project_membership_url, headers=pivotal_headers).format(project_id=project_id)
    for member in membership_response.json():
        person = member['person']

        if slack_email == person['email']:
            return person['id']


def get_slack_email(user_id):
    """Gets the Slack email associated with the Slack user id"""
    sc = SlackClient(deployed_slack_token)
    return sc.api_call(method='users.info', user=user_id)['user']['profile']['email']


def export_pairings():
    """Fetches all pairings from SimpleDB."""
    sdb_client = get_sdb_client()
    response = sdb_client.select(
        SelectExpression="select * from `{}`".format(sdb_domain))
    pair_dict = {
        item["Name"]: item["Attributes"][0]["Value"] for item in response["Items"]}

    return pair_dict


def lambda_handler(event, context):
    """Entrypoint for Lambda function. Contains core logic."""
    # TODO(Patrick): break up this function
    parsed_request = SlashCommandRequest(event, KNOWN_PHRASES)
    paired_tracker_project = get_channel_pairing(parsed_request.channel_id)

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
                logger.info(
                  "Attempting to pair channel {} to a Tracker project".format(
                    parsed_request.channel_id))
                project_id = get_pivotal_project_id(parsed_request.action_body)
                store_pairing(parsed_request.channel_id, project_id)
                project_name = get_project_name(project_id)
                return response(200, SUCCESSFUL_PAIR_RESPONSE.format(
                    project_name=project_name,
                    channel=parsed_request.formatted_channel,
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
    if len(parsed_request.text) == 0 or parsed_request.action_phrase == HELP_PHRASE:
        return response(
            200, TUTORIAL_RESPONSE.format(command=parsed_request.command))

    # User wants to unpair their current channel from a Tracker project
    if parsed_request.action_phrase == UNPAIR_PHRASE:
        project_name = get_project_name(paired_tracker_project)
        remove_pairing(parsed_request.channel_id, project_name)
        return response(200, SUCCESSFUL_UNPAIR_RESPONSE.format(
            project_name=project_name,
            channel=parsed_request.formatted_channel))

    # User wants to view the list of paired channels
    if parsed_request.action_phrase == EXPORT_PHRASE:
        pairing_dict = export_pairings()
        return response(200, EXPORT_PAIRINGS_RESPONSE.format(
            pairing_json=json.dumps(pairing_dict, sort_keys=True, indent=2)))

    # If no other actions were taken then we're posting a new Tracker story
    project_name = get_project_name(paired_tracker_project)
    story_name, story_url = post_new_tracker_story(
        parsed_request.text, paired_tracker_project, parsed_request.user, parsed_request.user_id)
    return response(200, SUCCESSFUL_POST_RESPONSE.format(
        story=story_name,
        project=project_name,
        url=story_url))
