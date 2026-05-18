# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  enable_deletion_protection = var.environment == "prod" ? true : false
  enable_http2              = true
  enable_cross_zone_load_balancing = true

  tags = {
    Name = "${var.project_name}-alb"
  }
}

# Target Group for API
resource "aws_lb_target_group" "api" {
  name        = "${var.project_name}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
  }

  tags = {
    Name = "${var.project_name}-api-tg"
  }
}

# Listener for HTTP (redirect to HTTPS in prod)
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = var.environment == "prod" ? "redirect" : "forward"
    
    dynamic "redirect" {
      for_each = var.environment == "prod" ? [1] : []
      content {
        port        = "443"
        protocol    = "HTTPS"
        status_code = "HTTP_301"
      }
    }

    dynamic "forward" {
      for_each = var.environment == "dev" ? [1] : []
      content {
        target_group {
          arn    = aws_lb_target_group.api.arn
          weight = 1
        }
      }
    }
  }
}

# CloudWatch Log Group for ALB
resource "aws_cloudwatch_log_group" "alb" {
  name              = "/aws/alb/${var.project_name}"
  retention_in_days = 7

  tags = {
    Name = "${var.project_name}-alb-logs"
  }
}

# ALB Logging (optional, for debugging)
resource "aws_lb" "main_with_logging" {
  count              = var.environment == "prod" ? 1 : 0
  name               = "${var.project_name}-alb-logs"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id

  access_logs {
    bucket  = aws_s3_bucket.alb_logs[0].id
    enabled = true
  }

  tags = {
    Name = "${var.project_name}-alb"
  }
}

# S3 Bucket for ALB logs (prod only)
resource "aws_s3_bucket" "alb_logs" {
  count  = var.environment == "prod" ? 1 : 0
  bucket = "${var.project_name}-alb-logs-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "${var.project_name}-alb-logs"
  }
}

# S3 Bucket Versioning
resource "aws_s3_bucket_versioning" "alb_logs" {
  count  = var.environment == "prod" ? 1 : 0
  bucket = aws_s3_bucket.alb_logs[0].id

  versioning_configuration {
    status = "Enabled"
  }
}

# S3 Bucket ACL
resource "aws_s3_bucket_acl" "alb_logs" {
  count  = var.environment == "prod" ? 1 : 0
  bucket = aws_s3_bucket.alb_logs[0].id
  acl    = "private"
}

# Get current AWS account ID
data "aws_caller_identity" "current" {}