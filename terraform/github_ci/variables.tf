# 리소스 이름에 사용할 프로젝트 이름
variable "project_name" {
  type = string
}

# 이미지 업로드를 허용할 ECR 저장소 ARN 목록
variable "ecr_repository_arns" {
  type = list(string)
}

# 이 저장소의 main 브랜치에서 발급한 인증 정보만 허용
# GitHub에서 확인한 계정 ID와 저장소 ID 포함
variable "github_oidc_subject" {
  type = string

  default = "repo:yonginfra@336437335/aws-msa-final-project@1416496287:ref:refs/heads/main"
}
