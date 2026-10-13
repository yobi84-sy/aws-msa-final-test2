# 운영 알림과 CloudWatch 경보 구성
module "monitoring" {
  source = "./monitoring"

  project_name = var.project_name
  alert_email  = var.alert_email

  account_id = data.aws_caller_identity.current.account_id

  order_queue_name = module.messaging.order_notifications_queue_name
  order_dlq_name   = module.messaging.order_notifications_dlq_name

  db_instance_identifier = module.rds.db_instance_identifier
  # 노드 생성 및 종료 알림에 사용할 ASG 이름 목록 전달
  node_group_asg_names = module.eks.node_group_asg_names

  # Alertmanager의 ServiceAccount 기반 AWS 인증에 사용
  oidc_provider_arn = module.eks.oidc_provider_arn
  oidc_issuer_url   = module.eks.oidc_issuer_url
}

# 운영 알림용 SNS 토픽 ARN
output "operations_alerts_topic_arn" {
  value = module.monitoring.alerts_topic_arn
}

# Alertmanager 설치 시 사용할 역할 ARN 확인
output "alertmanager_role_arn" {
  value = module.monitoring.alertmanager_role_arn
}
