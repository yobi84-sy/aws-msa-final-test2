# 주문 서비스가 기존 운영 알림 SNS에만 발행할 수 있도록 허용
resource "aws_iam_role_policy" "order_email_notifications" {
  name = "${var.project_name}-order-email-notifications"
  role = "${var.project_name}-ordering-sns-role"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sns:Publish"]
      Resource = module.monitoring.alerts_topic_arn
    }]
  })

  # IAM 역할을 생성한 뒤 정책 연결
  depends_on = [module.messaging]
}
