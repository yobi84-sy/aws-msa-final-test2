# EKS 노드 EC2 생성·종료·실패 이벤트를 운영 SNS로 전달
resource "aws_autoscaling_notification" "eks_nodes" {
  # EKS가 생성한 ASG 이름 목록에 알림 설정 적용
  group_names = var.node_group_asg_names

  # EC2 시작과 종료 및 각 작업의 실패 이벤트 구독
  notifications = [
    "autoscaling:EC2_INSTANCE_LAUNCH",
    "autoscaling:EC2_INSTANCE_TERMINATE",
    "autoscaling:EC2_INSTANCE_LAUNCH_ERROR",
    "autoscaling:EC2_INSTANCE_TERMINATE_ERROR",
  ]

  topic_arn = aws_sns_topic.operations_alerts.arn

  depends_on = [
    aws_sns_topic_policy.operations_alerts,
  ]
}
