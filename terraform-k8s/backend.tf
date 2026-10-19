# 버킷은 terraform-state-bootstrap에서 별도로 준비합니다. DynamoDB 없이 S3 네이티브 잠금 사용.
terraform {
  backend "s3" {
    bucket              = "final-tfstate-021158485482-ap-northeast-2"
    key                 = "final/k8s/terraform.tfstate"
    region              = "ap-northeast-2"
    profile             = "eks-user"
    encrypt             = true
    use_lockfile        = true
    allowed_account_ids = ["021158485482"]
  }
}
