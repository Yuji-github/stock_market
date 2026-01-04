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
# 3. S3 
# --------------------------------------------------------
resource "aws_s3_bucket" "stock_market_bucket" {
  bucket_prefix = "dash-app-stock-market-data" 
}

# Create the Instance Role (For the running app)
resource "aws_iam_role" "apprunner_instance_role" {
  name = "AppRunnerInstanceRole-DashApp"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "tasks.apprunner.amazonaws.com"
        }
      }
    ]
  })
}

# Create Policy to Allow S3 Write
resource "aws_iam_policy" "s3_write_policy" {
  name        = "AppRunnerS3WritePolicy"
  description = "Allow App Runner to write logs to S3"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:PutObject",
          "s3:ListBucket"
        ]
        Effect   = "Allow"
        Resource = [
          aws_s3_bucket.stock_market_bucket.arn,
          "${aws_s3_bucket.stock_market_bucket.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_s3_policy" {
  role       = aws_iam_role.apprunner_instance_role.name
  policy_arn = aws_iam_policy.s3_write_policy.arn
}
# --------------------------------------------------------
# 4. App Runner Service (The actual running app)
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
          GEMINI_API = var.google_api_key 
          JQUANTS_API = var.jqunats_api_key
          DASH_PASSWORD = var.dash_password
          S3_BUCKET_NAME = aws_s3_bucket.stock_market_bucket.bucket
        }
      }
    }
    
    auto_deployments_enabled = true
  }

  instance_configuration {
    cpu    = "1024" # 1 vCPU
    memory = "2048" # 2 GB
    instance_role_arn = aws_iam_role.apprunner_instance_role.arn
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

output "s3_bucket_name" {
  value       = aws_s3_bucket.stock_market_bucket.bucket
  description = "The actual name of the created S3 bucket"
}