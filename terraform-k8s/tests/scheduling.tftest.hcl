# Plan-only mocks: no AWS/Kubernetes/Helm changes or real credentials.
mock_provider "aws" {
  mock_data "aws_eks_cluster" {
    defaults = {
      endpoint              = "https://example.invalid"
      certificate_authority = [{ data = "dGVzdA==" }]
    }
  }
}
mock_provider "kubernetes" {}
mock_provider "helm" {}

override_data {
  target = data.terraform_remote_state.infra
  values = {
    outputs = {
      autoscaler_node_groups = {
        az-a = { asg_name = "mock-final-az-a", min_size = 2, max_size = 2 }
        az-c = { asg_name = "mock-final-az-c", min_size = 2, max_size = 3 }
      }
      db_address                        = "db.example.invalid"
      vpc_id                            = "vpc-0123456789abcdef0"
      cluster_autoscaler_role_arn       = "arn:aws:iam::143710973003:role/mock-ca"
      load_balancer_controller_role_arn = "arn:aws:iam::143710973003:role/mock-lb"
      alertmanager_role_arn             = "arn:aws:iam::143710973003:role/mock-alertmanager"
      operations_alerts_topic_arn       = "arn:aws:sns:ap-northeast-2:143710973003:mock-alerts"
      management_certificate_arn        = "arn:aws:acm:ap-northeast-2:143710973003:certificate/mock-management"
      website_certificate_arn           = "arn:aws:acm:ap-northeast-2:143710973003:certificate/mock-website"
    }
  }
}

variables {
  db_password               = "mock-password-only"
  github_token              = "mock-token-only"
  jwt_secret                = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
  jwt_refresh_secret        = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
  enable_management_ingress = true
  enable_app_sync           = true
}

run "zonal_scheduling" {
  command = plan

  assert {
    condition     = yamldecode(helm_release.cluster_autoscaler.values[0]).nodeSelector["final-node-pool"] == "az-a"
    error_message = "CA must stay in the new 2a pool."
  }
  assert {
    condition     = length(yamldecode(helm_release.cluster_autoscaler.values[0]).autoscalingGroups) == 2 && yamldecode(helm_release.cluster_autoscaler.values[0]).autoDiscovery.clusterName == ""
    error_message = "CA must manage exactly the two zonal groups, excluding the legacy group."
  }
  assert {
    condition     = sum([for group in yamldecode(helm_release.cluster_autoscaler.values[0]).autoscalingGroups : group.maxSize]) == 5
    error_message = "New pool maximum must remain five nodes total."
  }
  assert {
    condition     = yamldecode(helm_release.monitoring.values[1]).grafana.nodeSelector["final-node-pool"] == "az-c" && yamldecode(helm_release.monitoring.values[1]).prometheus.prometheusSpec.nodeSelector["final-node-pool"] == "az-c"
    error_message = "Grafana and Prometheus must remain in their EBS zone."
  }
  assert {
    condition     = yamldecode(helm_release.monitoring.values[1]).alertmanager.alertmanagerSpec.nodeSelector["final-node-pool"] == "az-a"
    error_message = "Alertmanager must remain in its existing EBS zone."
  }
  assert {
    condition     = yamldecode(helm_release.monitoring.values[1]).grafana.affinity == yamldecode(helm_release.monitoring.values[1]).prometheus.prometheusSpec.affinity && contains(yamldecode(helm_release.monitoring.values[1]).grafana.affinity.podAntiAffinity.requiredDuringSchedulingIgnoredDuringExecution[0].labelSelector.matchExpressions[1].values, "monitoring-kube-prometheus-prometheus")
    error_message = "Anti-affinity must match both actual workload labels."
  }
  assert {
    condition     = yamldecode(helm_release.monitoring.values[1]).prometheus.prometheusSpec.podAntiAffinity == ""
    error_message = "Disable the chart-generated anti-affinity so it cannot overwrite the custom rule."
  }
}
