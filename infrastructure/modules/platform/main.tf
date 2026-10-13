data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}
locals {
  name      = "cloudforge-${var.environment}"
  partition = data.aws_partition.current.partition
  account   = data.aws_caller_identity.current.account_id
  tags      = { Project = "cloudforge-aws", Environment = var.environment, ManagedBy = "Terraform" }
  logs_arn  = "arn:${local.partition}:logs:${var.region}:${local.account}:log-group:/aws/lambda/${local.name}-*:*"
  runtime = {
    TABLE_NAME         = module.table.name, UPLOAD_BUCKET = module.uploads.id,
    RESULT_BUCKET      = module.results.id, QUEUE_URL = module.queue.url,
    ENVIRONMENT        = var.environment, MAX_UPLOAD_BYTES = "10485760", MAX_ROWS = "100000",
    PROCESSING_SECONDS = "45", LEASE_SECONDS = "120", MAX_ATTEMPTS = "5"
  }
  database_statement = {
    Effect   = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query", "dynamodb:TransactWriteItems"],
    Resource = [module.table.arn, "${module.table.arn}/index/*"]
  }
  logs_statement = { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = [local.logs_arn] }
}
module "uploads" {
  source         = "../s3"
  name           = "${local.name}-${local.account}-${var.region}-uploads"
  tags           = local.tags
  retention_days = var.retention_days
  cors_origins   = var.origins
  eventbridge    = true
}
module "results" {
  source         = "../s3"
  name           = "${local.name}-${local.account}-${var.region}-results"
  tags           = local.tags
  retention_days = var.retention_days
  cors_origins   = var.origins
  eventbridge    = false
}
module "table" {
  source  = "../dynamodb"
  name    = local.name
  tags    = local.tags
  protect = var.protect_data
}
module "queue" {
  source         = "../sqs"
  name           = "${local.name}-jobs"
  tags           = local.tags
  worker_timeout = 60
}
module "events" {
  source    = "../eventbridge"
  name      = "${local.name}-uploads"
  bucket    = module.uploads.id
  queue_arn = module.queue.arn
  queue_url = module.queue.url
  tags      = local.tags
}
module "api_role" {
  source = "../iam"
  name   = "${local.name}-api"
  tags   = local.tags
  statements = [local.logs_statement, local.database_statement,
    { Effect = "Allow", Action = ["s3:PutObject"], Resource = ["${module.uploads.arn}/uploads/*"] },
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = ["${module.results.arn}/results/*"] },
  { Effect = "Allow", Action = ["sqs:GetQueueAttributes"], Resource = [module.queue.arn] }]
}
module "worker_role" {
  source = "../iam"
  name   = "${local.name}-worker"
  tags   = local.tags
  statements = [local.logs_statement, local.database_statement,
    { Effect = "Allow", Action = ["s3:GetObject", "s3:GetObjectVersion"], Resource = ["${module.uploads.arn}/uploads/*"] },
    { Effect = "Allow", Action = ["s3:PutObject"], Resource = ["${module.results.arn}/results/*"] },
  { Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"], Resource = [module.queue.arn] }]
}
module "api_function" {
  source      = "../lambda"
  name        = "${local.name}-api"
  role_arn    = module.api_role.arn
  artifact    = "${var.artifact_dir}/api.zip"
  handler     = "apps.api.handler.handler"
  environment = local.runtime
  timeout     = 10
  memory      = 256
  concurrency = var.api_concurrency
  retention   = var.log_retention
  tags        = local.tags
  depends_on  = [module.api_role]
}
module "worker_function" {
  source      = "../lambda"
  name        = "${local.name}-worker"
  role_arn    = module.worker_role.arn
  artifact    = "${var.artifact_dir}/worker.zip"
  handler     = "apps.worker.handler.handler"
  environment = local.runtime
  timeout     = 60
  memory      = var.worker_memory
  concurrency = var.worker_concurrency
  retention   = var.log_retention
  tags        = local.tags
  depends_on  = [module.worker_role]
}
resource "aws_lambda_event_source_mapping" "worker" {
  event_source_arn        = module.queue.arn
  function_name           = module.worker_function.alias_arn
  batch_size              = 1
  function_response_types = ["ReportBatchItemFailures"]
  scaling_config { maximum_concurrency = var.worker_concurrency }
}
module "auth" {
  source        = "../auth"
  name          = "${local.name}-${local.account}"
  callback_urls = var.callback_urls
  logout_urls   = var.logout_urls
  tags          = local.tags
}
module "api" {
  source      = "../api-gateway"
  name        = local.name
  lambda_name = module.api_function.name
  invoke_arn  = module.api_function.invoke_arn
  issuer      = "https://${module.auth.endpoint}"
  audience    = module.auth.client_id
  origins     = var.origins
  retention   = var.log_retention
  tags        = local.tags
}
module "observability" {
  source          = "../observability"
  name            = local.name
  environment     = var.environment
  api_id          = module.api.id
  api_function    = module.api_function.name
  worker_function = module.worker_function.name
  queue_name      = module.queue.name
  dead_name       = module.queue.dead_name
  table_name      = module.table.name
  alert_email     = var.alert_email
  tags            = local.tags
}
resource "aws_ssm_parameter" "api_url" {
  name  = "/${local.name}/api-url"
  type  = "String"
  value = module.api.url
  tags  = local.tags
}
