provider "aws" {
  region                      = "eu-central-1"
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
}

variables {
  name_prefix       = "pytorch-model-prod"
  oidc_issuer_url   = "https://oidc.eks.eu-central-1.amazonaws.com/id/EXAMPLE"
  oidc_provider_arn = "arn:aws:iam::123456789012:oidc-provider/oidc.eks.eu-central-1.amazonaws.com/id/EXAMPLE"

  app_service_accounts = {
    api = {
      namespace       = "pytorch-model-prod"
      service_account = "pytorch-model-api"
    }
    worker = {
      namespace       = "pytorch-model-prod"
      service_account = "pytorch-model-worker"
    }
  }

  model_runtime_service_accounts = {
    host = {
      namespace       = "pytorch-model-prod"
      service_account = "pytorch-model-model-runtime-host"
    }
  }

  app_runtime_policy_json = {
    api    = "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"sqs:SendMessage\"],\"Resource\":\"arn:aws:sqs:eu-central-1:123456789012:pytorch-model-prod-worker\"}]}"
    worker = "{\"Version\":\"2012-10-17\",\"Statement\":[{\"Effect\":\"Allow\",\"Action\":[\"sqs:ReceiveMessage\"],\"Resource\":\"arn:aws:sqs:eu-central-1:123456789012:pytorch-model-prod-worker\"}]}"
  }
}

run "plans_expected_workload_identity_resources" {
  command = plan

  assert {
    condition     = aws_iam_role.app["api"].name == "pytorch-model-prod-api"
    error_message = "API IRSA role must use the workload key in its name."
  }

  assert {
    condition     = aws_iam_role.app["worker"].name == "pytorch-model-prod-worker"
    error_message = "Worker IRSA role must use the workload key in its name."
  }

  assert {
    condition     = aws_iam_role.model_runtime.name == "pytorch-model-prod-model-service"
    error_message = "Model Runtime IRSA role must keep the stable model-service role name."
  }

  assert {
    condition     = contains(keys(output.role_arns), "api") && contains(keys(output.role_arns), "worker") && contains(keys(output.role_arns), "model_service")
    error_message = "role_arns output must match workload keys."
  }
}

run "plans_expected_irsa_trust_subjects" {
  command = plan

  assert {
    condition     = strcontains(aws_iam_role.app["api"].assume_role_policy, "system:serviceaccount:pytorch-model-prod:pytorch-model-api")
    error_message = "API role trust policy must include its Kubernetes service account subject."
  }

  assert {
    condition     = strcontains(aws_iam_role.app["worker"].assume_role_policy, "system:serviceaccount:pytorch-model-prod:pytorch-model-worker")
    error_message = "Worker role trust policy must include its Kubernetes service account subject."
  }

  assert {
    condition     = strcontains(aws_iam_role.model_runtime.assume_role_policy, "system:serviceaccount:pytorch-model-prod:pytorch-model-model-runtime-host")
    error_message = "Model Runtime role trust policy must include Model Runtime Host service account subject."
  }
}
