# Built-in Terraform state item, not an AWS resource. Check before charts create Services.
resource "terraform_data" "load_balancer_webhook_ready" {
  triggers_replace = [
    helm_release.load_balancer_controller.id,
    helm_release.load_balancer_controller.version,
    sha256(join("", helm_release.load_balancer_controller.values)),
    filesha256("${path.module}/../scripts/ops/wait_webhook.py")
  ]
  provisioner "local-exec" {
    command = "python \"${path.module}/../scripts/ops/wait_webhook.py\" --cluster \"${var.cluster_name}\" --profile \"${var.aws_profile}\" --region \"${var.aws_region}\""
  }
}
