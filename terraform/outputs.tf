output "worker_lambda_function_name" {
  description = "Name of the worker Lambda function"
  value       = aws_lambda_function.alervis_worker_lambda.function_name
}

output "worker_lambda_function_arn" {
  description = "ARN of the worker Lambda function"
  value       = aws_lambda_function.alervis_worker_lambda.arn
}

output "dispatch_lambda_function_name" {
  description = "Name of the dispatch Lambda function"
  value       = aws_lambda_function.alervis_dispatch_lambda.function_name
}

output "dispatch_lambda_function_arn" {
  description = "ARN of the dispatch Lambda function"
  value       = aws_lambda_function.alervis_dispatch_lambda.arn
}
