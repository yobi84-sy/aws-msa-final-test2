# 버킷은 terraform-state-bootstrap에서 별도로 준비합니다. DynamoDB 없이 S3 네이티브 잠금 사용.
terraform {
  backend "s3" {
    bucket              = "final-tfstate-143710973003-ap-northeast-2"
    key                 = "final/infra/terraform.tfstate"
    region              = "ap-northeast-2"
    profile             = "default"
    encrypt             = true
    use_lockfile        = true
    allowed_account_ids = ["143710973003"]
  }
}
