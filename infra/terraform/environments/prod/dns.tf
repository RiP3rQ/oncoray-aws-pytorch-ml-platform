resource "aws_route53_zone" "primary" {
  count = local.managed_zone_enabled ? 1 : 0

  name = local.managed_domain_name
}

resource "aws_acm_certificate" "frontend" {
  count    = var.enable_managed_acm_certificates && length(local.frontend_aliases) > 0 ? 1 : 0
  provider = aws.us_east_1

  domain_name               = local.frontend_aliases[0]
  subject_alternative_names = slice(local.frontend_aliases, 1, length(local.frontend_aliases))
  validation_method         = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_acm_certificate" "api" {
  count = var.enable_managed_acm_certificates && local.api_domain_name != "" ? 1 : 0

  domain_name       = local.api_domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

locals {
  frontend_certificate_validation_options = {
    for option in try(aws_acm_certificate.frontend[0].domain_validation_options, []) :
    option.domain_name => option
  }
  api_certificate_validation_options = {
    for option in try(aws_acm_certificate.api[0].domain_validation_options, []) :
    option.domain_name => option
  }
}

resource "aws_route53_record" "frontend_certificate_validation" {
  for_each = var.enable_managed_acm_certificates && length(local.frontend_aliases) > 0 ? toset(local.frontend_aliases) : toset([])

  zone_id = local.managed_zone_id
  name    = local.frontend_certificate_validation_options[each.key].resource_record_name
  type    = local.frontend_certificate_validation_options[each.key].resource_record_type
  ttl     = 60
  records = [local.frontend_certificate_validation_options[each.key].resource_record_value]
}

resource "aws_route53_record" "api_certificate_validation" {
  for_each = var.enable_managed_acm_certificates && local.api_domain_name != "" ? toset([local.api_domain_name]) : toset([])

  zone_id = local.managed_zone_id
  name    = local.api_certificate_validation_options[each.key].resource_record_name
  type    = local.api_certificate_validation_options[each.key].resource_record_type
  ttl     = 60
  records = [local.api_certificate_validation_options[each.key].resource_record_value]
}

resource "aws_acm_certificate_validation" "frontend" {
  count    = var.enable_managed_acm_certificates && length(local.frontend_aliases) > 0 ? 1 : 0
  provider = aws.us_east_1

  certificate_arn         = aws_acm_certificate.frontend[0].arn
  validation_record_fqdns = [for record in aws_route53_record.frontend_certificate_validation : record.fqdn]
}

resource "aws_acm_certificate_validation" "api" {
  count = var.enable_managed_acm_certificates && local.api_domain_name != "" ? 1 : 0

  certificate_arn         = aws_acm_certificate.api[0].arn
  validation_record_fqdns = [for record in aws_route53_record.api_certificate_validation : record.fqdn]
}
