# slack-pivotal-tracker-bot

Slack bot that helps you post new stories to Pivotal Tracker

## Set Up Development Environment

### Prerequisites

* Run `bin/prereqs` and install everything it tells you to. Then run `make deps`.
* [EditorConfig](http://editorconfig.org/) allows us to manage editor configuration (like indent sizes,) with a [file](https://github.com/transcom/ppp/blob/master/.editorconfig) in the repo. Install the appropriate plugin in your editor to take advantage of that.

### You'll need

1. Privileges to add a custom Slack integration
1. PivotalTracker API token (you'll find this in the account profile)
    * Trussels, we use the `trussbot@truss.works` account. Login credentials are in 1Password

### Terraform

1. `cd terraform/`
1. `terraform init`
1. `terraform get`
1. `terraform workspace list` (This project has both a test and prod environment)

## Initial Deployment

1. Create a Slack Outgoing WebHook (instructions below), leaving the URL field blank, but grab the slack API token
    * If you're onboarding to an existing deployment, just grab the existing API token
1. Copy `terraform/terraform.tfvars.example` to `terraform/terraform.tfvars` and fill in the variables as needed
1. Choose the deployment environment with `terraform workspace list` and `terraform workspace select <ENV>`
1. Run `make deploy` to build the Python code bundle and deploy via Terraform
1. Using the API Gateway trigger URL that was output by Terraform, update the Slack Webhook you created in step 1

### Creating a Slack Outgoing Webhook

1. Go to <https://YOURSLACK.slack.com/apps/build/custom-integration>
1. Outgoing WebHooks > Add Outgoing WebHooks integration
1. Channel: Any
1. Trigger Word(s): `!pivotal`
1. URL(s): [API Gateway Trigger URL (filled in after deployment)]

## Add New Project (Existing Setup)

1. Add `trussbot@truss.works` as a member of the Pivotal project you want to post to
1. Get PivotalTracker project URL from the project page, i.e. <https://www.pivotaltracker.com/n/projects/{PROJECT_ID}>
1. In the channel you want to pair, say `!pivotal pair {PROJECT_URL}`
1. If you want to remove the pairing later, just say `!pivotal unpair` in the same channel

## Terraform Docs

### Inputs

| Name | Description | Default | Required |
|------|-------------|:-----:|:-----:|
| pivotal_token | API Token for accessing pivotal projects | - | yes |
| region | AWS region | `us-west-2` | no |
| slack_token | API token for posting Slack messages | - | yes |

### Outputs

| Name | Description |
|------|-------------|
| slack_webhook_url |  |
