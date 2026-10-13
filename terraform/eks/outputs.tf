# 노드그룹 등에서 사용할 클러스터 이름
output "cluster_name" {
  value = aws_eks_cluster.main.name
}

# Kubernetes 관리 API 주소
output "cluster_endpoint" {
  value = aws_eks_cluster.main.endpoint
}

# EKS가 자동으로 만드는 클러스터 보안그룹 ID
output "cluster_security_group_id" {
  value = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
}

# 생성한 노드그룹 이름
output "node_group_name" {
  value = aws_eks_node_group.main.node_group_name
}

# 이후 CA 구성에서 참고할 Auto Scaling Group 이름 목록
output "node_group_asg_names" {
  value = flatten([
    for node_resource in aws_eks_node_group.main.resources : [
      for asg in node_resource.autoscaling_groups : asg.name
    ]
  ])
}

# 상품 서비스 IAM 역할에서 사용할 OIDC Provider ARN
output "oidc_provider_arn" {
  value = aws_iam_openid_connect_provider.main.arn
}

# 역할의 신뢰 조건에 사용할 토큰 발급자 주소
output "oidc_issuer_url" {
  value = aws_eks_cluster.main.identity[0].oidc[0].issuer
}
