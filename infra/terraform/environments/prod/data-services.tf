resource "random_password" "postgres" {
  count = var.db_password == "" ? 1 : 0

  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_security_group" "postgres" {
  name        = "${local.postgres_identifier}-sg"
  description = "Allow PostgreSQL access from within the production VPC"
  vpc_id      = module.vpc.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_subnet_group" "postgres" {
  name       = "${local.postgres_identifier}-subnets"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_vpc_security_group_ingress_rule" "postgres_from_eks_nodes" {
  security_group_id            = aws_security_group.postgres.id
  description                  = "Allow PostgreSQL from EKS nodes"
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  referenced_security_group_id = var.use_localstack ? "000000000000/${module.eks.node_security_group_id}" : module.eks.node_security_group_id
}

resource "aws_db_instance" "postgres" {
  identifier                   = local.postgres_identifier
  engine                       = "postgres"
  engine_version               = var.db_engine_version
  instance_class               = var.db_instance_class
  allocated_storage            = var.db_allocated_storage
  max_allocated_storage        = var.db_max_allocated_storage
  storage_type                 = "gp3"
  storage_encrypted            = true
  multi_az                     = true
  publicly_accessible          = false
  db_name                      = var.db_name
  username                     = var.db_username
  password                     = local.postgres_password
  db_subnet_group_name         = aws_db_subnet_group.postgres.name
  vpc_security_group_ids       = [aws_security_group.postgres.id]
  backup_retention_period      = var.db_backup_retention_period
  deletion_protection          = var.db_deletion_protection
  skip_final_snapshot          = var.db_skip_final_snapshot
  final_snapshot_identifier    = var.db_skip_final_snapshot ? null : "${local.postgres_identifier}-final"
  auto_minor_version_upgrade   = true
  copy_tags_to_snapshot        = true
  performance_insights_enabled = true

  depends_on = [module.vpc]
}
