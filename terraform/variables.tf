variable "pivotal_token" {
  description = "API Token for accessing pivotal projects"
}

variable "region" {
  description = "AWS region"
  type        = "string"
  default     = "us-west-2"
}

variable "slack_token" {
  description = "API token for posting Slack messages"
}
