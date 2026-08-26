output "skill_lambda_arns" {
  description = "ARN of each skill's Lambda, keyed by skill name"
  value       = { for k, v in module.alexa_skill : k => v.skill_lambda_arn }
}
