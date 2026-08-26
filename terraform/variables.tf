variable "aws_region" {
  type        = string
  description = "aws region"
  default     = "us-east-1"
}

variable "skills" {
  type = map(object({
    alexa_skill_id = string
    source_dir     = string
  }))
}
