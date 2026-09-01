data "archive_file" "skill_zip" {
  type        = "zip"
  source_dir  = var.source_dir
  output_path = "../lambda/artifacts/${var.skill_name}.zip"
}

resource "aws_iam_role" "skill_role" {
  name = "alervis_${var.skill_name}_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action    = "sts:AssumeRole"
        Effect    = "Allow"
        Sid       = ""
        Principal = { Service = "lambda.amazonaws.com" }
      },
    ]
  })
}

resource "aws_iam_role_policy_attachment" "skill_basic_execution" {
  role       = aws_iam_role.skill_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "skill_lambda" {
  function_name = "alervis_${var.skill_name}_function"
  role          = aws_iam_role.skill_role.arn

  filename         = data.archive_file.skill_zip.output_path
  source_code_hash = data.archive_file.skill_zip.output_base64sha256

  handler = "index.handler"
  runtime = "python3.12"
}

resource "aws_lambda_permission" "alexa_invoke" {
  statement_id       = "AllowExecutionFromAlexa"
  action             = "lambda:InvokeFunction"
  function_name      = aws_lambda_function.skill_lambda.function_name
  principal          = "alexa-appkit.amazon.com"
  event_source_token = var.alexa_skill_id
}
