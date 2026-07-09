terraform {
  required_version = ">= 1.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ─────────────────────────────────────────────
# Variables
# ─────────────────────────────────────────────
variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS deployment region"
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Deployment environment name"
}

variable "db_password" {
  type        = string
  default     = "KaosPassword123!"
  sensitive   = true
  description = "Database master password"
}

variable "confluent_bootstrap_servers" {
  type        = string
  description = "Confluent Cloud Kafka bootstrap server URL"
}

variable "confluent_api_key" {
  type        = string
  sensitive   = true
  description = "Confluent Cloud API Key"
}

variable "confluent_api_secret" {
  type        = string
  sensitive   = true
  description = "Confluent Cloud API Secret"
}

# ─────────────────────────────────────────────
# Networking (VPC & Subnets for RDS Free-Tier)
# ─────────────────────────────────────────────
resource "aws_vpc" "kaos_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "kaos-vpc-${var.environment}"
    Environment = var.environment
  }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.kaos_vpc.id
  tags = {
    Name = "kaos-igw"
  }
}

# Public Subnets (Where RDS resides to allow public access from Lambda without NAT Gateway)
resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.kaos_vpc.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.kaos_vpc.id
  cidr_block              = "10.0.2.0/24"
  availability_zone       = "${var.aws_region}b"
  map_public_ip_on_launch = true
}

# Route Tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.kaos_vpc.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.igw.id
  }
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

# Security Group for Public RDS Database
resource "aws_security_group" "db_sg" {
  name        = "kaos-db-sg"
  description = "Allow DB connection from allowed IPs and public egress"
  vpc_id      = aws_vpc.kaos_vpc.id

  # In production, restrict this CIDR block to specific trusted IPs / Lambda public CIDRs
  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow PostgreSQL connections"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ─────────────────────────────────────────────
# RDS PostgreSQL Instance (db.t3.micro Free-Tier)
# ─────────────────────────────────────────────
resource "aws_db_subnet_group" "db_subnets" {
  name       = "kaos-db-subnet-group"
  subnet_ids = [aws_subnet.public_a.id, aws_subnet.public_b.id]
}

resource "aws_db_instance" "postgres" {
  identifier             = "kaos-postgres-db"
  allocated_storage      = 20
  max_allocated_storage  = 100
  db_name                = "kaos_events"
  engine                 = "postgres"
  engine_version         = "17.5"
  instance_class         = "db.t3.micro" # 100% Free-Tier eligible for first 12 months
  username               = "kaos_user"
  password               = var.db_password
  db_subnet_group_name   = aws_db_subnet_group.db_subnets.name
  vpc_security_group_ids = [aws_security_group.db_sg.id]
  publicly_accessible    = true # Allows Lambda functions outside the VPC to connect
  skip_final_snapshot    = true

  tags = {
    Name = "kaos-events-db"
  }
}

# ─────────────────────────────────────────────
# Lambda Package (Zips up code repository)
# ─────────────────────────────────────────────
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/../../"
  output_path = "${path.module}/kaos_lambda.zip"
  excludes = [
    ".git",
    ".vscode",
    ".gemini",
    ".poetry",
    "tests",
    "deploy/terraform/kaos_lambda.zip",
    "deploy/terraform/kaos_layer.zip",
    "deploy/terraform/lambda_layer",
    "deploy/terraform/.terraform"
  ]
}

# Upload code zip to S3 (Lambda code > 70MB must use S3)
resource "aws_s3_object" "lambda_zip" {
  bucket = aws_s3_bucket.lambda_artifacts.id
  key    = "kaos_lambda.zip"
  source = data.archive_file.lambda_zip.output_path
  etag   = data.archive_file.lambda_zip.output_md5
}

# ─────────────────────────────────────────────
# S3 Bucket for Lambda artifacts (layer > 70MB)
# ─────────────────────────────────────────────
resource "aws_s3_bucket" "lambda_artifacts" {
  bucket        = "kaos-lambda-artifacts-${data.aws_caller_identity.current.account_id}"
  force_destroy = true

  tags = {
    Name        = "kaos-lambda-artifacts"
    Environment = var.environment
  }
}

data "aws_caller_identity" "current" {}

# ─────────────────────────────────────────────
# Lambda Layer (uploaded via S3 — supports >70MB)
# ─────────────────────────────────────────────
data "archive_file" "layer_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda_layer"
  output_path = "${path.module}/kaos_layer.zip"
}

resource "aws_s3_object" "layer_zip" {
  bucket = aws_s3_bucket.lambda_artifacts.id
  key    = "kaos_layer.zip"
  source = data.archive_file.layer_zip.output_path
  etag   = data.archive_file.layer_zip.output_md5
}

resource "aws_lambda_layer_version" "kaos_dependencies" {
  s3_bucket         = aws_s3_bucket.lambda_artifacts.id
  s3_key            = aws_s3_object.layer_zip.key
  layer_name        = "kaos-dependencies"
  compatible_runtimes = ["python3.12"]
  source_code_hash  = data.archive_file.layer_zip.output_base64sha256
}

# ─────────────────────────────────────────────
# IAM Role & Policies for Lambdas
# ─────────────────────────────────────────────
resource "aws_iam_role" "lambda_role" {
  name = "kaos-lambda-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Standard basic execution policy for CloudWatch logs
resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Bedrock invocation permission policy
resource "aws_iam_role_policy" "lambda_bedrock_policy" {
  name = "kaos-lambda-bedrock-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "*"
      }
    ]
  })
}

# Lambda IAM policy to access Secrets Manager for Kafka credentials
resource "aws_iam_role_policy" "lambda_secrets_policy" {
  name = "kaos-lambda-secrets-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          aws_secretsmanager_secret.confluent_creds.arn
        ]
      }
    ]
  })
}

# ─────────────────────────────────────────────
# Lambda Functions (Running outside VPC for free internet access)
# ─────────────────────────────────────────────
locals {
  common_env = {
    BOOTSTRAP_SERVERS      = var.confluent_bootstrap_servers
    SASL_USERNAME          = var.confluent_api_key
    SASL_PASSWORD          = var.confluent_api_secret
    SECURITY_PROTOCOL      = "SASL_SSL"
    SASL_MECHANISM         = "PLAIN"
    DATABASE_URL           = "postgresql://${aws_db_instance.postgres.username}:${var.db_password}@${aws_db_instance.postgres.endpoint}/${aws_db_instance.postgres.db_name}"
    USE_BEDROCK_EMBEDDINGS = "true"
  }
}

# 1. Triager Lambda
resource "aws_lambda_function" "triager" {
  function_name    = "kaos-triager"
  handler          = "agents.triager.lambda_handler.handler"
  runtime          = "python3.12"
  role             = aws_iam_role.lambda_role.arn
  s3_bucket        = aws_s3_bucket.lambda_artifacts.id
  s3_key           = aws_s3_object.lambda_zip.key
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 60
  memory_size      = 512
  layers           = [aws_lambda_layer_version.kaos_dependencies.arn]

  environment {
    variables = local.common_env
  }
}

# 2. Review Manager Lambda
resource "aws_lambda_function" "review_manager" {
  function_name    = "kaos-review-manager"
  handler          = "agents.review_manager.lambda_handler.handler"
  runtime          = "python3.12"
  role             = aws_iam_role.lambda_role.arn
  s3_bucket        = aws_s3_bucket.lambda_artifacts.id
  s3_key           = aws_s3_object.lambda_zip.key
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 90
  memory_size      = 512
  layers           = [aws_lambda_layer_version.kaos_dependencies.arn]

  environment {
    variables = local.common_env
  }
}

# 3. Ops Manager Lambda
resource "aws_lambda_function" "ops_manager" {
  function_name    = "kaos-ops-manager"
  handler          = "agents.ops_manager.lambda_handler.handler"
  runtime          = "python3.12"
  role             = aws_iam_role.lambda_role.arn
  s3_bucket        = aws_s3_bucket.lambda_artifacts.id
  s3_key           = aws_s3_object.lambda_zip.key
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 90
  memory_size      = 512
  layers           = [aws_lambda_layer_version.kaos_dependencies.arn]

  environment {
    variables = local.common_env
  }
}

# 4. Ingestion Webhook Lambda
resource "aws_lambda_function" "ingestion" {
  function_name    = "kaos-ingestion"
  handler          = "agents.ingestion.lambda_handler.handler"
  runtime          = "python3.12"
  role             = aws_iam_role.lambda_role.arn
  s3_bucket        = aws_s3_bucket.lambda_artifacts.id
  s3_key           = aws_s3_object.lambda_zip.key
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 30
  memory_size      = 256
  layers           = [aws_lambda_layer_version.kaos_dependencies.arn]

  environment {
    variables = local.common_env
  }
}

# 5. Chatbot Lambda
resource "aws_lambda_function" "chatbot" {
  function_name    = "kaos-chatbot"
  handler          = "agents.chatbot.lambda_handler.handler"
  runtime          = "python3.12"
  role             = aws_iam_role.lambda_role.arn
  s3_bucket        = aws_s3_bucket.lambda_artifacts.id
  s3_key           = aws_s3_object.lambda_zip.key
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 90
  memory_size      = 512
  layers           = [aws_lambda_layer_version.kaos_dependencies.arn]

  environment {
    variables = local.common_env
  }
}

# ─────────────────────────────────────────────
# API Gateway HTTP API (Exposes Ingestion, Chatbot, & Agents)
# ─────────────────────────────────────────────
resource "aws_apigatewayv2_api" "gateway" {
  name          = "kaos-api-gateway"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.gateway.id
  name        = "$default"
  auto_deploy = true
}

# Integrations helper template
# 1. Ingestion FastAPI
resource "aws_apigatewayv2_integration" "ingestion" {
  api_id             = aws_apigatewayv2_api.gateway.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.ingestion.arn
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "ingestion_webhooks" {
  api_id    = aws_apigatewayv2_api.gateway.id
  route_key = "POST /webhooks/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.ingestion.id}"
}

# 2. Chatbot FastAPI
resource "aws_apigatewayv2_integration" "chatbot" {
  api_id             = aws_apigatewayv2_api.gateway.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.chatbot.arn
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "chatbot_chat" {
  api_id    = aws_apigatewayv2_api.gateway.id
  route_key = "POST /chat"
  target    = "integrations/${aws_apigatewayv2_integration.chatbot.id}"
}

# 3. Triager HTTP Invocator
resource "aws_apigatewayv2_integration" "triager" {
  api_id             = aws_apigatewayv2_api.gateway.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.triager.arn
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "triager_route" {
  api_id    = aws_apigatewayv2_api.gateway.id
  route_key = "POST /agents/triager"
  target    = "integrations/${aws_apigatewayv2_integration.triager.id}"
}

# 4. Review Manager HTTP Invocator
resource "aws_apigatewayv2_integration" "review_manager" {
  api_id             = aws_apigatewayv2_api.gateway.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.review_manager.arn
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "review_manager_route" {
  api_id    = aws_apigatewayv2_api.gateway.id
  route_key = "POST /agents/review-manager"
  target    = "integrations/${aws_apigatewayv2_integration.review_manager.id}"
}

# 5. Ops Manager HTTP Invocator
resource "aws_apigatewayv2_integration" "ops_manager" {
  api_id             = aws_apigatewayv2_api.gateway.id
  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.ops_manager.arn
  integration_method = "POST"
}

resource "aws_apigatewayv2_route" "ops_manager_route" {
  api_id    = aws_apigatewayv2_api.gateway.id
  route_key = "POST /agents/ops-manager"
  target    = "integrations/${aws_apigatewayv2_integration.ops_manager.id}"
}

# APIGW permissions to invoke Lambdas
resource "aws_lambda_permission" "apigw_ingestion" {
  statement_id  = "AllowAPIGatewayInvokeIngestion"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.gateway.execution_arn}/*/*"
}

resource "aws_lambda_permission" "apigw_chatbot" {
  statement_id  = "AllowAPIGatewayInvokeChatbot"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.chatbot.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.gateway.execution_arn}/*/*"
}

resource "aws_lambda_permission" "apigw_triager" {
  statement_id  = "AllowAPIGatewayInvokeTriager"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.triager.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.gateway.execution_arn}/*/*"
}

resource "aws_lambda_permission" "apigw_review_manager" {
  statement_id  = "AllowAPIGatewayInvokeReviewManager"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.review_manager.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.gateway.execution_arn}/*/*"
}

resource "aws_lambda_permission" "apigw_ops_manager" {
  statement_id  = "AllowAPIGatewayInvokeOpsManager"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ops_manager.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.gateway.execution_arn}/*/*"
}

# ─────────────────────────────────────────────
# Secrets Manager & AWS Lambda Event Source Mapping (Kafka)
# ─────────────────────────────────────────────

# Store Confluent credentials in Secrets Manager for Lambda ESM
resource "aws_secretsmanager_secret" "confluent_creds" {
  name                    = "kaos/confluent/kafka_creds_${data.aws_caller_identity.current.account_id}"
  recovery_window_in_days = 0 # Force delete immediately for easy teardown
}

resource "aws_secretsmanager_secret_version" "confluent_creds_val" {
  secret_id = aws_secretsmanager_secret.confluent_creds.id
  secret_string = jsonencode({
    username = var.confluent_api_key
    password = var.confluent_api_secret
  })
}

# Triager Kafka Trigger
resource "aws_lambda_event_source_mapping" "triager_kafka" {
  function_name     = aws_lambda_function.triager.arn
  topics            = ["system.quality.reports"]
  starting_position = "LATEST"

  self_managed_event_source {
    endpoints = {
      KAFKA_BOOTSTRAP_SERVERS = var.confluent_bootstrap_servers
    }
  }
  source_access_configuration {
    type = "BASIC_AUTH"
    uri  = aws_secretsmanager_secret.confluent_creds.arn
  }
}

# Review Manager Kafka Trigger - PR Updates
resource "aws_lambda_event_source_mapping" "review_mgr_kafka_updates" {
  function_name     = aws_lambda_function.review_manager.arn
  topics            = ["dev.pr.updates"]
  starting_position = "LATEST"

  self_managed_event_source {
    endpoints = {
      KAFKA_BOOTSTRAP_SERVERS = var.confluent_bootstrap_servers
    }
  }
  source_access_configuration {
    type = "BASIC_AUTH"
    uri  = aws_secretsmanager_secret.confluent_creds.arn
  }
}

# Review Manager Kafka Trigger - PR Decisions
resource "aws_lambda_event_source_mapping" "review_mgr_kafka_decisions" {
  function_name     = aws_lambda_function.review_manager.arn
  topics            = ["dev.pr.decisions"]
  starting_position = "LATEST"

  self_managed_event_source {
    endpoints = {
      KAFKA_BOOTSTRAP_SERVERS = var.confluent_bootstrap_servers
    }
  }
  source_access_configuration {
    type = "BASIC_AUTH"
    uri  = aws_secretsmanager_secret.confluent_creds.arn
  }
}

# Ops Manager Kafka Trigger - Deploy Status
resource "aws_lambda_event_source_mapping" "ops_mgr_kafka_deploy" {
  function_name     = aws_lambda_function.ops_manager.arn
  topics            = ["ops.deploy.status"]
  starting_position = "LATEST"

  self_managed_event_source {
    endpoints = {
      KAFKA_BOOTSTRAP_SERVERS = var.confluent_bootstrap_servers
    }
  }
  source_access_configuration {
    type = "BASIC_AUTH"
    uri  = aws_secretsmanager_secret.confluent_creds.arn
  }
}

# Ops Manager Kafka Trigger - Incidents
resource "aws_lambda_event_source_mapping" "ops_mgr_kafka_incidents" {
  function_name     = aws_lambda_function.ops_manager.arn
  topics            = ["ops.incidents"]
  starting_position = "LATEST"

  self_managed_event_source {
    endpoints = {
      KAFKA_BOOTSTRAP_SERVERS = var.confluent_bootstrap_servers
    }
  }
  source_access_configuration {
    type = "BASIC_AUTH"
    uri  = aws_secretsmanager_secret.confluent_creds.arn
  }
}

# ─────────────────────────────────────────────
# Outputs
# ─────────────────────────────────────────────
output "api_gateway_url" {
  value       = aws_apigatewayv2_stage.default.invoke_url
  description = "Base URL for the API Gateway webhooks and agent endpoints"
}

output "postgres_db_endpoint" {
  value       = aws_db_instance.postgres.endpoint
  description = "RDS Postgres database connection endpoint"
}
