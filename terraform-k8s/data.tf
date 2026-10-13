# 기존 AWS 인프라의 Terraform 결과 조회
# AWS 폴더에서 apply를 완료한 뒤 사용할 수 있음
data "terraform_remote_state" "infra" {
  backend = "local"

  config = {
    # 상대 경로를 절대 경로로 변환
    path = abspath("${path.module}/../terraform/terraform.tfstate")
  }
}
