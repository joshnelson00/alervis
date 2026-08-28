terraform {
  required_version = ">= 1.5.0"

  cloud {
    organization = "josh-personal"
    workspaces {
      name = "alervis"
    }
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "<= 6.61"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.8"
    }
  }
}
