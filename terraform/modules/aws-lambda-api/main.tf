variable "name" {
  type        = "string"
  description = "Name of your Lambda API gateway"
}

variable "region" {
  type        = "string"
  description = "The AWS region, e.g., us-west-2"
}

variable "role" {
  type        = "string"
  description = "Role for lambda function"
}

variable "http_method" {
  type        = "string"
  description = "HTTP method for trigger API gateway"
}

variable "handler" {
  type        = "string"
  description = "Lambda request handler"
}

variable "runtime" {
  type        = "string"
  default     = "python2.7"
  description = "Lambda runtime"
}

variable "timeout" {
  type        = "string"
  default     = "3"
  description = "Lambda function timeout"
}

variable "filename" {
  type        = "string"
  description = "File path to lambda deployment artifact"
}

variable "lambda_env_var" {
  type        = "map"
  default     = {}
  description = "Environment variables for lambda function"
}

/*
 * IAM
 */

// Get the access to the effective Account ID in which Terraform is working
data "aws_caller_identity" "current" {}

/*
 * Lambda
 */

resource "aws_lambda_function" "lambda" {
  filename         = "${var.filename}"
  function_name    = "${var.name}"
  role             = "${var.role}"
  handler          = "${var.handler}"
  runtime          = "${var.runtime}"
  timeout          = "${var.timeout}"
  source_code_hash = "${base64sha256(file(var.filename))}"

  environment = {
    variables = "${var.lambda_env_var}"
  }
}

/*
 * API Gateway
 */

resource "aws_api_gateway_rest_api" "lambda_api" {
  name = "${var.name} API"
}

resource "aws_api_gateway_resource" "lambda_api_res" {
  rest_api_id = "${aws_api_gateway_rest_api.lambda_api.id}"
  parent_id   = "${aws_api_gateway_rest_api.lambda_api.root_resource_id}"
  path_part   = "${var.name}"
}

resource "aws_api_gateway_method" "request_method" {
  rest_api_id   = "${aws_api_gateway_rest_api.lambda_api.id}"
  resource_id   = "${aws_api_gateway_resource.lambda_api_res.id}"
  http_method   = "${var.http_method}"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "request_method_integration" {
  rest_api_id = "${aws_api_gateway_rest_api.lambda_api.id}"
  resource_id = "${aws_api_gateway_resource.lambda_api_res.id}"
  http_method = "${aws_api_gateway_method.request_method.http_method}"
  type        = "AWS_PROXY"
  uri         = "arn:aws:apigateway:${var.region}:lambda:path/2015-03-31/functions/${aws_lambda_function.lambda.arn}/invocations"

  # AWS lambdas can only be invoked with the POST method
  integration_http_method = "POST"
}

resource "aws_api_gateway_method_response" "response_method" {
  rest_api_id = "${aws_api_gateway_rest_api.lambda_api.id}"
  resource_id = "${aws_api_gateway_resource.lambda_api_res.id}"
  http_method = "${aws_api_gateway_integration.request_method_integration.http_method}"
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }
}

resource "aws_api_gateway_integration_response" "response_method_integration" {
  rest_api_id = "${aws_api_gateway_rest_api.lambda_api.id}"
  resource_id = "${aws_api_gateway_resource.lambda_api_res.id}"
  http_method = "${aws_api_gateway_method_response.response_method.http_method}"
  status_code = "${aws_api_gateway_method_response.response_method.status_code}"

  response_templates = {
    "application/json" = ""
  }
}

resource "aws_lambda_permission" "allow_api_gateway" {
  function_name = "${aws_lambda_function.lambda.function_name}"
  statement_id  = "AllowExecutionFromApiGateway"
  action        = "lambda:InvokeFunction"
  principal     = "apigateway.amazonaws.com"
  source_arn    = "arn:aws:execute-api:${var.region}:${data.aws_caller_identity.current.account_id}:${aws_api_gateway_rest_api.lambda_api.id}/*/${aws_api_gateway_integration.request_method_integration.http_method}${aws_api_gateway_resource.lambda_api_res.path}"
}

// The ID of the API gateway REST API
output "id" {
  value = "${aws_api_gateway_rest_api.lambda_api.id}"
}

// Name of the Lambda function
output "name" {
  value = "${aws_lambda_function.lambda.function_name}"
}
