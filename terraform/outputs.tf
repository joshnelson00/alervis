output "lambda_function_name" {
  description = "Name of the deployed Lambda function"
  value       = aws_lambda_function.alervis_lambda.function_name
}

output "lambda_function_arn" {
  description = "ARN of the deployed Lambda function"
  value       = aws_lambda_function.alervis_lambda.arn
}
