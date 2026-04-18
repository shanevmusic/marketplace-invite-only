# ----------------------------------------------------------------------------
# CloudWatch Dashboard — v1 operator cockpit
# ----------------------------------------------------------------------------
# Single dashboard with the signals an on-call operator checks first:
#   • ALB request volume + 5xx rate  (traffic + errors)
#   • ALB target-response-time p95   (latency)
#   • ECS service CPU + memory       (capacity)
#   • ECS running task count         (availability)
#
# Custom application metrics (ws_connections_active, orders_placed, …) are
# produced by the Prometheus exporter at /metrics; exporting them to
# CloudWatch requires the OTEL sidecar, which is tracked in
# docs/POST-V1-BACKLOG.md as a v1.1 follow-up.  Until then this dashboard
# is the authoritative infra-side view.
# ----------------------------------------------------------------------------

resource "aws_cloudwatch_dashboard" "ops" {
  dashboard_name = "${local.name_prefix}-ops"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "ALB — Requests / minute"
          region = var.aws_region
          view   = "timeSeries"
          stat   = "Sum"
          period = 60
          metrics = [
            [
              "AWS/ApplicationELB",
              "RequestCount",
              "LoadBalancer",
              aws_lb.this.arn_suffix,
            ],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "ALB — 5xx rate"
          region = var.aws_region
          view   = "timeSeries"
          stat   = "Sum"
          period = 60
          metrics = [
            [
              "AWS/ApplicationELB",
              "HTTPCode_Target_5XX_Count",
              "LoadBalancer",
              aws_lb.this.arn_suffix,
            ],
            [
              ".",
              "HTTPCode_ELB_5XX_Count",
              ".",
              ".",
            ],
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "ALB — Target response time (p95)"
          region = var.aws_region
          view   = "timeSeries"
          stat   = "p95"
          period = 60
          metrics = [
            [
              "AWS/ApplicationELB",
              "TargetResponseTime",
              "LoadBalancer",
              aws_lb.this.arn_suffix,
            ],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "ECS — running task count"
          region = var.aws_region
          view   = "timeSeries"
          stat   = "Average"
          period = 60
          metrics = [
            [
              "ECS/ContainerInsights",
              "RunningTaskCount",
              "ClusterName",
              aws_ecs_cluster.this.name,
              "ServiceName",
              aws_ecs_service.backend.name,
            ],
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "ECS — CPU utilization"
          region = var.aws_region
          view   = "timeSeries"
          stat   = "Average"
          period = 60
          metrics = [
            [
              "AWS/ECS",
              "CPUUtilization",
              "ClusterName",
              aws_ecs_cluster.this.name,
              "ServiceName",
              aws_ecs_service.backend.name,
            ],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 12
        width  = 12
        height = 6
        properties = {
          title  = "ECS — Memory utilization"
          region = var.aws_region
          view   = "timeSeries"
          stat   = "Average"
          period = 60
          metrics = [
            [
              "AWS/ECS",
              "MemoryUtilization",
              "ClusterName",
              aws_ecs_cluster.this.name,
              "ServiceName",
              aws_ecs_service.backend.name,
            ],
          ]
        }
      },
    ]
  })
}
