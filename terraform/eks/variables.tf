# 클러스터 이름
variable "cluster_name" {
  type = string
}

# Kubernetes 버전
variable "cluster_version" {
  type = string
}

# EKS 서비스가 사용할 IAM 역할
variable "cluster_role_arn" {
  type = string
}

# 클러스터가 사용할 프라이빗 서브넷 목록
variable "private_subnet_ids" {
  type = list(string)
}

# 외부 관리 API 접속 허용 대역
variable "public_access_cidrs" {
  type = list(string)
}

# 클러스터 관리자 접근 권한을 부여할 대상
variable "admin_principal_arn" {
  type = string
}

# EC2 노드가 사용할 IAM 역할
variable "node_role_arn" {
  type = string
}

# 노드 인스턴스 종류
variable "node_instance_types" {
  type = list(string)
}

# 초기 노드 수
variable "node_desired_size" {
  type = number
}

# 최소 노드 수
variable "node_min_size" {
  type = number
}

# 최대 노드 수
variable "node_max_size" {
  type = number
}
