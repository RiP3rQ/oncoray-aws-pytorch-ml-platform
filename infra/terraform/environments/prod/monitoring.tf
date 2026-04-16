locals {
  redis_cache_cluster_ids = [
    for idx in range(var.redis_num_cache_clusters) : format("%s-%03d", local.redis_replication_group_id, idx + 1)
  ]
}

resource "aws_cloudwatch_metric_alarm" "sqs_visible_messages" {
  alarm_name          = "${local.name_prefix}-worker-queue-depth"
  alarm_description   = "Worker queue depth is above the production threshold."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Average"
  threshold           = 25
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    QueueName = aws_sqs_queue.worker.name
  }
}

resource "aws_cloudwatch_metric_alarm" "sqs_oldest_message" {
  alarm_name          = "${local.name_prefix}-worker-queue-age"
  alarm_description   = "Worker queue oldest message age is above the production threshold."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ApproximateAgeOfOldestMessage"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 300
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    QueueName = aws_sqs_queue.worker.name
  }
}

resource "aws_cloudwatch_metric_alarm" "sqs_dlq_visible_messages" {
  alarm_name          = "${local.name_prefix}-worker-dlq-depth"
  alarm_description   = "Worker DLQ has visible messages."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 0
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    QueueName = aws_sqs_queue.worker_dlq.name
  }
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
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

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
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

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
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    DBInstanceIdentifier = aws_db_instance.postgres.identifier
  }
}

resource "aws_cloudwatch_metric_alarm" "redis_cpu" {
  for_each = toset(local.redis_cache_cluster_ids)

  alarm_name          = "${each.value}-cpu"
  alarm_description   = "ElastiCache CPU utilization is above the production threshold."
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Average"
  threshold           = 75
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    CacheClusterId = each.value
  }
}

resource "aws_cloudwatch_metric_alarm" "redis_memory" {
  for_each = toset(local.redis_cache_cluster_ids)

  alarm_name          = "${each.value}-freeable-memory"
  alarm_description   = "ElastiCache freeable memory is below the production threshold."
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 2
  metric_name         = "FreeableMemory"
  namespace           = "AWS/ElastiCache"
  period              = 300
  statistic           = "Minimum"
  threshold           = 100000000
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    CacheClusterId = each.value
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
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

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
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    LoadBalancer = var.api_alb_arn_suffix
    TargetGroup  = var.api_target_group_arn_suffix
  }
}

resource "aws_cloudwatch_metric_alarm" "eks_failed_nodes" {
  count = var.enable_container_insights_node_condition_alarm ? 1 : 0

  alarm_name          = "${local.name_prefix}-eks-failed-nodes"
  alarm_description   = "EKS cluster has worker nodes reporting failure conditions through Container Insights."
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 2
  metric_name         = "cluster_failed_node_count"
  namespace           = "ContainerInsights"
  period              = 60
  statistic           = "Maximum"
  threshold           = 1
  treat_missing_data  = "notBreaching"
  alarm_actions       = var.alarm_actions
  ok_actions          = var.ok_actions

  dimensions = {
    ClusterName = module.eks.cluster_name
  }
}
