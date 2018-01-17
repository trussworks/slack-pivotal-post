terraform {
  required_version = "~> 0.10"

  backend "s3" {
    bucket  = "truss-terraform-state"
    key     = "truss/aws-us-west-2/bang_pivotal/terraform.tfstate"
    region  = "us-west-2"
    encrypt = "true"
  }
}

/*
 * SimpleDB
 */

resource "aws_simpledb_domain" "bang_pivotal" {
  name = "bang_pivotal_${terraform.env}"
}

/*
 * IAM
 */

data "aws_iam_policy_document" "lambda_trust_document" {
  statement {
    actions = ["sts:AssumeRole"]

    principals = {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "iam_role_for_lambda" {
  name               = "iam_role_for_bang_pivotal_${terraform.env}"
  assume_role_policy = "${data.aws_iam_policy_document.lambda_trust_document.json}"
}

data "aws_iam_policy_document" "lambda_role_policy_document" {
  statement {
    actions = [
      "sdb:GetAttributes",
      "sdb:PutAttributes",
      "sdb:DeleteAttributes",
    ]

    effect = "Allow"

    resources = [
      "arn:aws:sdb:*:*:domain/${aws_simpledb_domain.bang_pivotal.id}",
    ]
  }

  statement {
    actions = [
      "logs:CreateLogGroup",
    ]

    effect = "Allow"

    resources = [
      "arn:aws:logs:*:*",
    ]
  }

  statement {
    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    effect = "Allow"

    resources = [
      "arn:aws:logs:*:*:*:*",
    ]
  }
}

resource "aws_iam_policy" "lambda_policy" {
  name   = "iam_policy_for_bang_pivotal_${terraform.env}"
  policy = "${data.aws_iam_policy_document.lambda_role_policy_document.json}"
}

resource "aws_iam_role_policy_attachment" "test-attach" {
  role       = "${aws_iam_role.iam_role_for_lambda.name}"
  policy_arn = "${aws_iam_policy.lambda_policy.arn}"
}

/*
 * Lambda + API Gateway
 */

module "bang_pivotal_post" {
  source      = "modules/aws-lambda-api"
  name        = "bang_pivotal_${terraform.env}"
  role        = "${aws_iam_role.iam_role_for_lambda.arn}"
  region      = "${var.region}"
  http_method = "POST"
  handler     = "handler.lambda_handler"
  runtime     = "python3.6"
  timeout     = "10"
  filename    = "../src/bundle.zip"

  lambda_env_var = {
    slack_token   = "${var.slack_token}"
    pivotal_token = "${var.pivotal_token}"
    sdb_domain    = "${aws_simpledb_domain.bang_pivotal.id}"
  }
}

resource "aws_api_gateway_deployment" "bang_pivotal_api_deployment" {
  depends_on  = ["module.bang_pivotal_post"]
  rest_api_id = "${module.bang_pivotal_post.id}"
  stage_name  = "${terraform.env}"
  description = "Deploy methods: POST"
}

output "slack_webhook_url" {
  value = "https://${module.bang_pivotal_post.id}.execute-api.us-west-2.amazonaws.com/${terraform.env}/${module.bang_pivotal_post.name}"
}
