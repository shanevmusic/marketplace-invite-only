# AWS Terraform — ECS Fargate stack

This stack provisions the production backend runtime.  It does **not** create
the Supabase database (Supabase manages that) — the task reaches Supabase over
the public internet (TLS) using the pooled connection string stored in
Secrets Manager.

## Directory map

```
main.tf              # ECS cluster, service, ALB, S3, IAM, alarms
variables.tf         # All inputs (with sane defaults)
outputs.tf           # ECR URL, ALB DNS, secret ARNs, etc.
providers.tf         # AWS provider + default tags
versions.tf          # Required providers + backend stub
terraform.tfvars.example
```

## Prerequisites

1. An ACM certificate in the deployment region for your API hostname.
2. An S3 bucket + DynamoDB table if you uncomment the `backend "s3"` block
   in `versions.tf`.
3. AWS credentials with sufficient privileges (administrator or a scoped
   role) for the principal running `terraform apply`.

## Usage

```bash
cd infra/terraform/aws
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars — at minimum set acm_cert_arn

terraform init
terraform validate
terraform plan -out=tfplan
terraform apply tfplan
```

## Secrets Manager → container env mapping

Terraform creates empty secret *slots* with names like
`marketplace-prod/jwt_secret_primary`.  After the first apply, populate each
value out-of-band so plaintext never lands in state:

```bash
aws secretsmanager put-secret-value \
  --secret-id marketplace-prod/jwt_secret_primary \
  --secret-string "$(openssl rand -base64 48)"
```

| Container env var              | Secrets Manager key                         | Purpose                          |
|--------------------------------|---------------------------------------------|----------------------------------|
| `APP_JWT_SECRET_PRIMARY`       | `marketplace-<env>/jwt_secret_primary`      | HS256 signing key                |
| `APP_JWT_SECRET_SECONDARY`     | `marketplace-<env>/jwt_secret_secondary`    | Rotation verifier                |
| `APP_DB_PASSWORD`              | `marketplace-<env>/db_password`             | Supabase service password        |
| `APP_FCM_SERVER_KEY`           | `marketplace-<env>/fcm_server_key`          | Android push                     |
| `APP_APNS_KEY_PEM`             | `marketplace-<env>/apns_key_pem`            | iOS push key                     |
| `APP_APNS_KEY_ID`              | `marketplace-<env>/apns_key_id`             | iOS push key ID                  |
| `APP_APNS_TEAM_ID`             | `marketplace-<env>/apns_team_id`            | Apple team ID                    |
| `APP_SENTRY_DSN`               | `marketplace-<env>/sentry_dsn`              | Error reporting                  |
| `APP_METRICS_TOKEN`            | `marketplace-<env>/metrics_token`           | Shared secret for `/metrics`     |

Non-secret env vars (`APP_ENVIRONMENT`, `APP_S3_BUCKET`, `APP_S3_REGION`)
are set directly in the task definition.

Vars you must also set at runtime but which are not managed here (either
derived or dev-only): `APP_DATABASE_URL`, `APP_DATABASE_URL_SYNC`,
`APP_CORS_ORIGINS`, `APP_S3_CDN_BASE_URL`.  Set these in the task
definition `environment` block in `main.tf` once values are known.

## Resources produced

- `module.vpc`                        2 AZ VPC + NAT
- `aws_ecr_repository.backend`        ECR image store
- `aws_ecs_cluster.this`              Fargate cluster
- `aws_ecs_task_definition.backend`   1 vCPU / 2 GB task
- `aws_ecs_service.backend`           Service fronted by ALB
- `aws_lb.this` / `aws_lb_listener.https` / `aws_lb_target_group.backend`
- `aws_s3_bucket.uploads`             Uploads bucket (versioned, SSE)
- `aws_iam_role.task_execution`       Pulls image + reads secrets
- `aws_iam_role.task`                 S3/SES/SNS access for the app
- `aws_cloudwatch_log_group.backend`  30-day log retention
- `aws_cloudwatch_metric_alarm.*`     5xx, CPU, memory
- `aws_appautoscaling_policy.cpu`     2-10 tasks on CPU > 70%
- `aws_secretsmanager_secret.app_secrets[*]`

## Validation without applying

`terraform validate` only checks syntax + provider schema.  It does **not**
require AWS credentials.  CI runs `terraform fmt -check && terraform
validate` (see `.github/workflows/test.yml`).

## OIDC trust policy for CI

GitHub Actions pushes images and updates the ECS service via a role that
trusts `token.actions.githubusercontent.com`:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "arn:aws:iam::<acct>:oidc-provider/token.actions.githubusercontent.com" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": { "token.actions.githubusercontent.com:aud": "sts.amazonaws.com" },
      "StringLike":  { "token.actions.githubusercontent.com:sub": "repo:shanevmusic/marketplace-invite-only:ref:refs/heads/main" }
    }
  }]
}
```

Attach a policy granting `ecr:*` on the `marketplace-backend` repo,
`ecs:UpdateService`, `ecs:RunTask`, `iam:PassRole` on the task/execution
roles, and `logs:*` on the log group.  Store the role ARN as the
`AWS_OIDC_ROLE_ARN` GitHub secret.
