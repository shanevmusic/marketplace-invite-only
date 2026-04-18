output "ecr_repository_url" {
  description = "ECR repo URL for CI image pushes."
  value       = aws_ecr_repository.backend.repository_url
}

output "alb_dns_name" {
  description = "Public hostname of the ALB."
  value       = aws_lb.this.dns_name
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "ecs_service_name" {
  value = aws_ecs_service.backend.name
}

output "uploads_bucket_name" {
  value = aws_s3_bucket.uploads.bucket
}

output "task_execution_role_arn" {
  value = aws_iam_role.task_execution.arn
}

output "task_role_arn" {
  value = aws_iam_role.task.arn
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.backend.name
}

output "secret_arns" {
  description = "Map of Secrets Manager secret name -> ARN."
  value       = { for k, v in aws_secretsmanager_secret.app_secrets : k => v.arn }
}
