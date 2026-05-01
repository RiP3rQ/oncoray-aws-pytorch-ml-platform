function New-TerraformOutput {
    param([Parameter(Mandatory = $true)][object]$Value)

    return @{
        value = $Value
    }
}

function New-TerraformOutputsFixture {
    return @{
        aws_region                      = New-TerraformOutput -Value "eu-central-1"
        cluster_name                    = New-TerraformOutput -Value "pytorch-model-prod-eks"
        vpc_id                          = New-TerraformOutput -Value "vpc-123"
        api_waf_acl_arn                 = New-TerraformOutput -Value "arn:aws:wafv2:api"
        frontend_bucket_name            = New-TerraformOutput -Value "frontend-bucket"
        frontend_distribution_id        = New-TerraformOutput -Value "EDFDVBD6EXAMPLE"
        prediction_artifacts_bucket_name = New-TerraformOutput -Value "artifact-bucket"
        worker_queue_url                = New-TerraformOutput -Value "https://sqs.example/worker"
        worker_dlq_url                  = New-TerraformOutput -Value "https://sqs.example/worker-dlq"
        redis                           = New-TerraformOutput -Value @{
            primary_endpoint = "redis-primary.example"
            reader_endpoint  = "redis-reader.example"
            port             = 6379
        }
        ecr_repository_urls             = New-TerraformOutput -Value @{
            api           = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/pytorch-model/api"
            model_service = "123456789012.dkr.ecr.eu-central-1.amazonaws.com/pytorch-model/model-service"
        }
        cluster_addon_role_arns         = New-TerraformOutput -Value @{
            aws_load_balancer_controller = "arn:aws:iam::123456789012:role/alb"
            external_secrets             = "arn:aws:iam::123456789012:role/external-secrets"
            fluent_bit                   = "arn:aws:iam::123456789012:role/fluent-bit"
        }
        app_workload_role_arns          = New-TerraformOutput -Value @{
            api           = "arn:aws:iam::123456789012:role/api"
            worker        = "arn:aws:iam::123456789012:role/worker"
            model_service = "arn:aws:iam::123456789012:role/model-service"
        }
        kubernetes_service_accounts     = New-TerraformOutput -Value @{
            namespace      = "pytorch-model-prod"
            api            = "pytorch-model-api"
            worker         = "pytorch-model-worker"
            model_service  = "pytorch-model-model-service"
            model_runtimes = @{
                effnetb0 = "pytorch-model-model-service-effnetb0"
                vitb16   = "pytorch-model-model-service-vitb16"
            }
        }
        expected_parameter_store_paths  = New-TerraformOutput -Value @{
            api                   = @("/pytorch-model/prod/api/SECRET_KEY")
            worker                = @("/pytorch-model/prod/worker/SQS_QUEUE_URL")
            model_service_effnetb0 = @("/pytorch-model/prod/model-service-effnetb0/HF_TOKEN")
            model_service_vitb16   = @("/pytorch-model/prod/model-service-vitb16/HF_TOKEN")
        }
    }
}
