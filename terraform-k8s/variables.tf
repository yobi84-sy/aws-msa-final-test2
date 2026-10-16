# AWS 서울 리전
variable "aws_region" {
  type    = string
  default = "ap-northeast-2"
}

# 기존 Terraform과 동일한 AWS CLI 프로필
variable "aws_profile" {
  type    = string
  default = "default"
}

# 내부 도구를 설치할 EKS 클러스터 이름
variable "cluster_name" {
  type    = string
  default = "Final-eks"
}

# Argo CD가 읽을 GitHub 저장소
variable "github_repo_url" {
  type    = string
  default = "https://github.com/yonginfra/aws-msa-final-project.git"
}

# 저장소 읽기 토큰을 발급한 GitHub 사용자
variable "github_revision" {
  description = "Argo CD가 배포할 Git 브랜치 또는 커밋. 기본은 main, 별도 검증은 test 사용."
  type        = string
  default     = "main"
}

# 저장소 읽기 토큰을 발급한 GitHub 사용자
variable "github_username" {
  type    = string
  default = "yonginfra"
}

# 실행할 때만 전달하고 Terraform 상태 파일에는 저장하지 않음
variable "github_token" {
  type      = string
  sensitive = true
  ephemeral = true
}

# RDS 생성 시 사용한 비밀번호를 앱에도 동일하게 전달
variable "db_password" {
  type      = string
  sensitive = true
  ephemeral = true
}

# 회원 서비스와 API Gateway가 공유하는 JWT 서명 키
variable "jwt_secret" {
  type      = string
  sensitive = true
  ephemeral = true

  validation {
    condition     = length(var.jwt_secret) >= 88 && can(regex("^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$", var.jwt_secret))
    error_message = "JWT 서명 키는 64바이트 이상의 값을 Base64로 인코딩하세요. Prepare-Secrets.ps1로 생성할 수 있습니다."
  }
}

# 회원 서비스의 Refresh Token 서명 키
variable "jwt_refresh_secret" {
  type      = string
  sensitive = true
  ephemeral = true

  validation {
    condition     = length(var.jwt_refresh_secret) >= 88 && can(regex("^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$", var.jwt_refresh_secret))
    error_message = "Refresh Token 서명 키는 64바이트 이상의 값을 Base64로 인코딩하세요. Prepare-Secrets.ps1로 생성할 수 있습니다."
  }
}

# 비밀번호나 JWT 키를 변경할 때 이 번호도 증가
variable "app_secret_revision" {
  type    = number
  default = 1

  validation {
    condition     = var.app_secret_revision >= 1 && floor(var.app_secret_revision) == var.app_secret_revision
    error_message = "Secret 변경 번호는 1 이상의 정수여야 합니다."
  }
}

# 이미지 업로드와 Secret 준비를 마친 뒤 true로 변경
variable "enable_app_sync" {
  type    = bool
  default = false
}

# 관리 화면 인증서 발급을 완료한 뒤 true로 설정
variable "enable_management_ingress" {
  type    = bool
  default = false
}
