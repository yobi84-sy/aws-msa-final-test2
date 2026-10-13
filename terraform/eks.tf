# 네트워크와 IAM 역할을 EKS 모듈에 전달
module "eks" {
  source = "./eks"

  cluster_name    = var.eks_cluster_name
  cluster_version = var.eks_cluster_version

  cluster_role_arn   = module.iam.eks_cluster_role_arn
  private_subnet_ids = module.network.private_subnet_ids

  public_access_cidrs = var.eks_public_access_cidrs
  admin_principal_arn = var.eks_admin_principal_arn

  # 노드그룹 설정
  node_role_arn       = module.iam.eks_node_role_arn
  node_instance_types = var.eks_node_instance_types

  node_desired_size = var.eks_node_desired_size
  node_min_size     = var.eks_node_min_size
  node_max_size     = var.eks_node_max_size

  # IAM 정책 연결과 네트워크 구성이 끝난 뒤 생성
  depends_on = [
    module.iam,
    module.network
  ]
}
