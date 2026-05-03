locals {
  cloudwatch_alarm_actions = length(var.alarm_email_addresses) > 0 ? [aws_sns_topic.cloudwatch_alarms[0].arn] : []
  cloudwatch_ok_actions    = local.cloudwatch_alarm_actions
}

resource "aws_sns_topic" "cloudwatch_alarms" {
  count = length(var.alarm_email_addresses) > 0 ? 1 : 0

  name = "${local.name_prefix}-cloudwatch-alarms"
}

resource "aws_sns_topic_subscription" "cloudwatch_alarm_email" {
  for_each = toset(var.alarm_email_addresses)

  topic_arn = aws_sns_topic.cloudwatch_alarms[0].arn
  protocol  = "email"
  endpoint  = each.value
}

resource "aws_cloudwatch_metric_alarm" "rds_cpu" {
  alarm_name          = "${local.name_prefix}-postgres-cpu"
  alarm_description   = "RDS CPU utilization is above the production threshold."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.cloudwatch_alarm_actions
  ok_actions          = local.cloudwatch_ok_actions

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.postgres.identifier
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_storage" {
  alarm_name          = "${local.name_prefix}-postgres-free-storage"
  alarm_description   = "RDS free storage is below the production threshold."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Minimum"
  threshold           = 5368709120
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.cloudwatch_alarm_actions
  ok_actions          = local.cloudwatch_ok_actions

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.postgres.identifier
  }
}

resource "aws_cloudwatch_metric_alarm" "rds_connections" {
  alarm_name          = "${local.name_prefix}-postgres-connections"
  alarm_description   = "RDS connection count is above the production threshold."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.cloudwatch_alarm_actions
  ok_actions          = local.cloudwatch_ok_actions

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.postgres.identifier
  }
}

resource "aws_cloudwatch_metric_alarm" "api_target_5xx" {
  count = var.api_alb_arn_suffix != "" && var.api_target_group_arn_suffix != "" ? 1 : 0

  alarm_name          = "${local.name_prefix}-api-target-5xx"
  alarm_description   = "API ALB target 5xx responses are above the production threshold."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "HTTPCode_Target_5XX_Count"
  namespace           = "AWS/ApplicationELB"
  period              = 300
  statistic           = "Sum"
  threshold           = 5
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.cloudwatch_alarm_actions
  ok_actions          = local.cloudwatch_ok_actions

  dimensions = {
    LoadBalancer = var.api_alb_arn_suffix
    TargetGroup  = var.api_target_group_arn_suffix
  }
}

resource "aws_cloudwatch_metric_alarm" "api_unhealthy_targets" {
  count = var.api_alb_arn_suffix != "" && var.api_target_group_arn_suffix != "" ? 1 : 0

  alarm_name          = "${local.name_prefix}-api-unhealthy-targets"
  alarm_description   = "API ALB has unhealthy targets."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "UnHealthyHostCount"
  namespace           = "AWS/ApplicationELB"
  period              = 60
  statistic           = "Average"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.cloudwatch_alarm_actions
  ok_actions          = local.cloudwatch_ok_actions

  dimensions = {
    LoadBalancer = var.api_alb_arn_suffix
    TargetGroup  = var.api_target_group_arn_suffix
  }
}

resource "aws_cloudwatch_metric_alarm" "eks_failed_nodes" {
  count = var.enable_container_insights_node_condition_alarm ? 1 : 0

  alarm_name          = "${local.name_prefix}-eks-failed-nodes"
  alarm_description   = "EKS cluster has nodes reporting failure conditions through Container Insights."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "cluster_failed_node_count"
  namespace           = "ContainerInsights"
  period              = 60
  statistic           = "Maximum"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = local.cloudwatch_alarm_actions
  ok_actions          = local.cloudwatch_ok_actions

  dimensions = {
    ClusterName = module.eks.cluster_name
  }
}

resource "aws_cloudwatch_log_group" "api_waf" {
  count = var.enable_api_waf ? 1 : 0

  name              = "aws-waf-logs-${local.name_prefix}-api"
  retention_in_days = var.log_retention_in_days
}

resource "aws_cloudwatch_log_group" "frontend_waf" {
  count    = var.enable_frontend_waf ? 1 : 0
  provider = aws.us_east_1

  name              = "aws-waf-logs-${local.name_prefix}-frontend"
  retention_in_days = var.log_retention_in_days
}

resource "aws_wafv2_web_acl_logging_configuration" "api" {
  count = var.enable_api_waf ? 1 : 0

  log_destination_configs = [aws_cloudwatch_log_group.api_waf[0].arn]
  resource_arn            = aws_wafv2_web_acl.api[0].arn

  redacted_fields {
    single_header {
      name = "authorization"
    }
  }

  redacted_fields {
    single_header {
      name = "cookie"
    }
  }
}

resource "aws_wafv2_web_acl_logging_configuration" "frontend" {
  count    = var.enable_frontend_waf ? 1 : 0
  provider = aws.us_east_1

  log_destination_configs = [aws_cloudwatch_log_group.frontend_waf[0].arn]
  resource_arn            = aws_wafv2_web_acl.frontend[0].arn
}
