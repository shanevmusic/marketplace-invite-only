provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "marketplace"
      Environment = var.environment
      ManagedBy   = "terraform"
      Component   = "backend"
    }
  }
}
