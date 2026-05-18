variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Environment (dev/staging/prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name"
  type        = string
  default     = "fintech-fraud-detection"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "azs" {
  description = "Availability zones"
  type        = list(string)
  default     = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
}

variable "private_subnets" {
  description = "Private subnet CIDR blocks"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "public_subnets" {
  description = "Public subnet CIDR blocks"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}
variable "db_password" {
  description = "Database password"
  type        = string
  sensitive   = true
  default     = "ChangeMe123!@#"  # À changer en prod
}

variable "db_instance_class" {
  description = "DB instance class"
  type        = string
  default     = "db.t3.micro"
}
variable "redis_auth_token" {
  description = "Redis auth token"
  type        = string
  sensitive   = true
  default     = "RedisToken123!@#456"  # À changer en prod
}
variable "kubernetes_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.26"
}

variable "eks_instance_type" {
  description = "EKS node instance type"
  type        = string
  default     = "t3.small"
}

variable "eks_desired_size" {
  description = "EKS desired number of nodes"
  type        = number
  default     = 3
}

variable "eks_min_size" {
  description = "EKS minimum number of nodes"
  type        = number
  default     = 2
}

variable "eks_max_size" {
  description = "EKS maximum number of nodes"
  type        = number
  default     = 10
}