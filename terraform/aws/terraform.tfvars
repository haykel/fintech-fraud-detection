aws_region   = "eu-west-1"
environment  = "dev"
project_name = "fintech-fraud-detection"

vpc_cidr = "10.0.0.0/16"

azs = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]

public_subnets = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]

db_password      = "PostgresSecure123!@#"
db_instance_class = "db.t3.micro"

redis_auth_token = "RedisSecure123!@#"

kubernetes_version = "1.28"
eks_instance_type  = "t3.medium"
eks_desired_size   = 3
eks_min_size       = 2
eks_max_size       = 10