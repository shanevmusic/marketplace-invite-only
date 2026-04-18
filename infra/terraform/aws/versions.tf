terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Uncomment when ready to use a remote backend.
  # backend "s3" {
  #   bucket         = "marketplace-tfstate"
  #   key            = "aws/ecs/terraform.tfstate"
  #   region         = "us-east-1"
  #   dynamodb_table = "marketplace-tfstate-lock"
  #   encrypt        = true
  # }
}
