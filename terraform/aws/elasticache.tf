# ElastiCache Subnet Group
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-redis-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = {
    Name = "${var.project_name}-redis-subnet-group"
  }
}

# ElastiCache Redis Cluster
resource "aws_elasticache_cluster" "main" {
  cluster_id           = "${var.project_name}-redis"
  engine               = "redis"
  node_type            = var.environment == "prod" ? "cache.t3.small" : "cache.t3.micro"
  num_cache_nodes      = var.environment == "prod" ? 3 : 1
  parameter_group_name = "default.redis7"
  engine_version       = "7.0"
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  snapshot_retention_limit = var.environment == "prod" ? 30 : 0
  snapshot_window          = "03:00-05:00"

  maintenance_window = "sun:05:00-sun:07:00"

  tags = {
    Name = "${var.project_name}-redis"
  }
}

# CloudWatch Log Group for Redis
resource "aws_cloudwatch_log_group" "redis_slow_log" {
  name              = "/aws/elasticache/${var.project_name}-redis-slow-log"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-redis-slow-log"
  }
}