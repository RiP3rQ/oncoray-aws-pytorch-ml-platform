check "expected_aws_account" {
  assert {
    condition = (
      var.expected_aws_account_id == "" ||
      var.use_localstack ||
      data.aws_caller_identity.current.account_id == var.expected_aws_account_id
    )
    error_message = "AWS caller account does not match expected_aws_account_id."
  }
}

check "expected_aws_principal" {
  assert {
    condition = (
      var.expected_aws_principal_arn == "" ||
      var.use_localstack ||
      data.aws_caller_identity.current.arn == var.expected_aws_principal_arn
    )
    error_message = "AWS caller ARN does not match expected_aws_principal_arn."
  }
}
