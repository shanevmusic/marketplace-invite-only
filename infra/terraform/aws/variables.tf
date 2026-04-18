variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment name (dev | staging | prod)."
  type        = string
  default     = "prod"
}

variable "app_name" {
  description = "Short application name, used as a prefix for most resources."
  type        = string
  default     = "marketplace"
}

variable "image_tag" {
  description = "ECR image tag to deploy (set by CI/CD)."
  type        = string
  default     = "latest"
}

variable "service_desired_count" {
  description = "Initial number of ECS tasks."
  type        = number
  default     = 2
}

variable "service_min_count" {
  description = "Minimum tasks for autoscaling."
  type        = number
  default     = 2
}

variable "service_max_count" {
  description = "Maximum tasks for autoscaling."
  type        = number
  default     = 10
}

variable "task_cpu" {
  description = "Fargate task CPU units (1024 = 1 vCPU)."
  type        = number
  default     = 1024
}

variable "task_memory" {
  description = "Fargate task memory (MiB)."
  type        = number
  default     = 2048
}

variable "acm_cert_arn" {
  description = "ACM certificate ARN for the ALB HTTPS listener."
  type        = string
  default     = ""
}

variable "hosted_zone_id" {
  description = "Optional Route53 hosted zone ID.  Empty disables DNS."
  type        = string
  default     = ""
}

variable "dns_name" {
  description = "Fully-qualified hostname to register with Route53."
  type        = string
  default     = ""
}

variable "ops_alert_sns_arn" {
  description = "SNS topic ARN for CloudWatch alarms.  Empty disables alarms."
  type        = string
  default     = ""
}

variable "log_retention_days" {
  description = "CloudWatch log retention (days)."
  type        = number
  default     = 30
}

variable "container_port" {
  description = "Port the backend container listens on."
  type        = number
  default     = 8000
}
