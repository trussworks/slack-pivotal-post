# DEPRECATION NOTICE
This project is no longer being maintained.

# slack-pivotal-tracker-bot [![CircleCI Status](https://circleci.com/gh/trussworks/slack-pivotal-tracker-bot.svg?style=shield&circle-token=:circle-token)](https://circleci.com/gh/trussworks/slack-pivotal-tracker-bot)

Post new Pivotal Tracker stories directly from Slack

## Deployment

You can deploy this bot using the accompanying public [Terraform module](https://github.com/trussworks/terraform-slack-pivotal-tracker-bot).

## Usage

After you've deployed this bot as a [slash command](https://api.slack.com/slash-commands), there's only one more step to start posting stories:

### Pair

Internally this bot maintains a mapping of Slack channels to Pivotal Tracker projects, so to start you'll need to set up your first pairing. Be sure to use the full Tracker project URL and not just the project ID:

<!-- markdownlint-disable MD034 -->
> /pivotal pair https://www.pivotaltracker.com/n/projects/1234567

<!-- markdownlint-enable MD034 -->

### Post

Now you're ready to start posting stories! Any text after your keyphrase will become the title of your story, and optionally you can specify the story description with a semicolon:

<!-- markdownlint-disable MD028 -->
> /pivotal Make a user feedback page

> /pivotal Make a user feedback page; Use /feedback route and add name/address to the form

<!-- markdownlint-disable MD028 -->

### Unpair

Maybe you're done with a project, or you just want to change Tracker projects. Use `unpair` for that:

> /pivotal unpair

### Help

And if you ever forget how to use this bot, just ask for help:

> /pivotal help

## Development

The following instructions assume that you're developing on a Mac running a fairly recent version of OS X.

### Getting Started

There's a few prerequisite tools you'll need to start contributing. Run `bin/prereqs` to find out what your machine needs.

### Installation

Run `pre-commit install` to set up a pre-commit hook, and run `make deps` to install the python dependencies

### Testing

We use [pytest](https://docs.pytest.org/en/latest/) as our testing framework. Run the tests with `make test`.

## License

This project is licensed under BSD 3-clause license - see the [LICENSE.md](LICENSE.md) file for details
