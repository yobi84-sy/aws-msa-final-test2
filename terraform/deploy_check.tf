# 게시 역할과 분리된 배포 조회 전용 역할. 쓰기/Secret 조회 권한은 부여하지 않습니다.
resource "aws_iam_role" "deploy_check" {
  name = "${var.project_name}-github-deploy-check-role"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect    = "Allow", Principal = { Federated = module.github_ci.oidc_provider_arn }, Action = "sts:AssumeRoleWithWebIdentity",
    Condition = { StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com", "token.actions.githubusercontent.com:sub" = "repo:yobi84-sy@306224385/aws-msa-final-test2@1425236181:ref:refs/heads/main" } }
  }] })
}
resource "aws_iam_role_policy" "deploy_check" {
  role   = aws_iam_role.deploy_check.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "eks:DescribeCluster", Resource = module.eks.cluster_arn }] })
}
resource "aws_eks_access_entry" "deploy_check" {
  cluster_name      = module.eks.cluster_name
  principal_arn     = aws_iam_role.deploy_check.arn
  kubernetes_groups = ["final-deploy-readers"]
  type              = "STANDARD"
}
output "github_deploy_check_role_arn" { value = aws_iam_role.deploy_check.arn }
