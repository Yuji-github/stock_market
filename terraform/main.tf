provider "aws" {
  region = "ap-northeast-1" 
}

# --------------------------------------------------------
# 1. ECR Repository 
# --------------------------------------------------------
resource "aws_ecr_repository" "app_repo" {
  name                 = "dash-workspace-repo"
  image_tag_mutability = "MUTABLE"
  force_delete         = true # Allows deleting repo even if images exist (good for dev)

  image_scanning_configuration {
    scan_on_push = true
  }
}

# --------------------------------------------------------
# 2. IAM Role (Permission for App Runner to pull images)
# --------------------------------------------------------
resource "aws_iam_role" "apprunner_access_role" {
  name = "AppRunnerECRAccessRole-DashWorkspace"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "build.apprunner.amazonaws.com"
        }
      }
    ]
  })
}

# Attach the AWS managed policy that gives ECR pull access
resource "aws_iam_role_policy_attachment" "apprunner_access_policy" {
  role       = aws_iam_role.apprunner_access_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# --------------------------------------------------------
# 3. App Runner Service (The actual running app)
# --------------------------------------------------------
resource "aws_apprunner_service" "dash_service" {
  service_name = "dash-workspace-service"

  # Wait for the image to exist! 
  # If you run this before pushing the image, it might fail.
  depends_on = [aws_ecr_repository.app_repo] 

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_access_role.arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.app_repo.repository_url}:latest"
      image_repository_type = "ECR"

      image_configuration {
        port = "8050" # Matches your Dash app
        
        # Environment variables for your app
        runtime_environment_variables = {
          ENV = "production"
          GOOGLE_API_KEY = var.google_api_key 
          JQUANTS_API = var.jqunats_api_key
          DASH_PASSWORD = var.dash_password
        }
      }
    }
    
    auto_deployments_enabled = true
  }

  instance_configuration {
    cpu    = "1024" # 1 vCPU
    memory = "2048" # 2 GB
  }
}

# --------------------------------------------------------
# Outputs
# --------------------------------------------------------
output "ecr_repo_url" {
  value = aws_ecr_repository.app_repo.repository_url
}

output "app_runner_url" {
  value = aws_apprunner_service.dash_service.service_url
}