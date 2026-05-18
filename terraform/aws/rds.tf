# RDS Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = {
    Name = "${var.project_name}-db-subnet-group"
  }
}

# RDS PostgreSQL Instance
resource "aws_db_instance" "main" {
  identifier     = "${var.project_name}-postgres"
  engine         = "postgres"
  engine_version = "15.3"
  instance_class = var.environment == "prod" ? "db.t3.small" : "db.t3.micro"

  allocated_storage     = 20
  storage_type          = "gp3"
  storage_encrypted     = true
  iops                  = 3000
  
  db_name  = "fintech_db"
  username = "postgres"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  multi_az            = var.environment == "prod" ? true : false
  publicly_accessible = false
  skip_final_snapshot = true

  backup_retention_period = 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"

  enabled_cloudwatch_logs_exports = ["postgresql"]
  
  deletion_protection = var.environment == "prod" ? true : false

  tags = {
    Name = "${var.project_name}-postgres"
  }
}