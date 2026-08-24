provider "aws" {
  region = var.aws_region
}

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "../lambda/index.py"
  output_path = "../lambda_function.zip"
}

resource "aws_iam_role" "alervis_role" {
  name = "alervis_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Sid    = ""
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      },
    ]
  })
}

resource "aws_lambda_function" "alervis_lambda" {
  function_name = "alervis_function"
  role          = aws_iam_role.alervis_role.arn

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  handler = "index.handler"
  runtime = "python3.12"
}
