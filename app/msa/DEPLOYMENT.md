# 배포 준비 메모

이 파일은 실행 순서 참고용이다. 현재 AWS 적용/이미지 업로드/클러스터 설치는 하지 않았다.
GitHub/Notion에 올릴 프로젝트 설명은 프로젝트 완성 후 따로 정리한다.

## 준비된 구성

- 앱 배포 목록: `C:\aws-msa-backend-terraform\app\msa\kustomization.yaml`
- 상품 S3/주문 SNS용 ServiceAccount와 기존 Terraform IAM 역할 연결.
- 앱 4개 ServiceMonitor 수집과 노드/파드 지표, SNS 경보 규칙 4개.
- Prometheus 5Gi, Grafana 1Gi, Alertmanager 1Gi의 gp3 영구 저장 설정.
- Argo CD 단일 복제, 불필요한 SSO/알림 구성 제외, 관리 화면은 port-forward.
- CI 템플릿: 다섯 이미지 빌드 → ECR 업로드 → Git의 이미지 태그 변경 → Argo CD 자동 동기화.
- AWS 계정: 143710973003, 리전: ap-northeast-2, 클러스터: Final-eks.

## AWS 적용 후 진행할 순서

PowerShell에서 한 단계씩 결과를 확인한다. Helm CLI는 별도로 설치해야 한다.
검증용으로 내려받은 helm.exe는 Codex 작업 폴더에만 있으며 시스템 PATH에 설치하지 않았다.

1. Terraform apply 결과와 SNS 이메일 구독 확인.
2. `aws eks update-kubeconfig --region ap-northeast-2 --name Final-eks`
3. `kubectl apply -f C:\aws-msa-backend-terraform\app\msa\k8s\namespaces.yml`
4. 아래 명령으로 비밀번호/JWT Secret 생성. 비밀번호는 실행 중 입력하고 파일에 저장하지 않는다.

```powershell
$dbHostValue = terraform -chdir=C:\aws-msa-backend-terraform\terraform output -raw db_address
& C:\aws-msa-backend-terraform\app\msa\scripts\New-AppSecret.ps1 -DbHost $dbHostValue
```

5. 이미지 업로드. 다섯 이미지가 모두 올라가야 앱을 배포한다.

```powershell
& C:\aws-msa-backend-terraform\app\msa\scripts\Build-Images.ps1 -Push
```

6. CA를 적용하고 ASG 탐색 태그/권한 및 로그를 확인한다.

```powershell
kubectl apply -f C:\aws-msa-backend-terraform\app\msa\k8s\autoscaler\autoscaler.yml
kubectl logs -n kube-system deployment/cluster-autoscaler --tail=50
```

7. Helm 저장소 등록 후 ALB Controller 설치. 버전은 기존 IAM 정책과 맞춘다.

```powershell
helm repo add eks https://aws.github.io/eks-charts
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add argo https://argoproj.github.io/argo-helm
helm repo update
$vpcIdValue = terraform -chdir=C:\aws-msa-backend-terraform\terraform output -raw vpc_id
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller --version 3.6.0 --namespace kube-system --values C:\aws-msa-backend-terraform\app\msa\k8s\lb-controller\controller-values.yml --set vpcId=$vpcIdValue --wait --timeout 10m
```

8. StorageClass와 모니터링 설치. EBS CSI 애드온이 정상인지 먼저 확인한다.

```powershell
kubectl apply -f C:\aws-msa-backend-terraform\app\msa\k8s\storage\storageclass.yml
helm upgrade --install monitoring prometheus-community/kube-prometheus-stack --version 92.3.0 --namespace monitoring --values C:\aws-msa-backend-terraform\app\msa\k8s\k8s-monitoring\monitoring-values.yml --wait --timeout 10m
```

9. 앱 배포와 상태 확인. 모니터링/Argo CD/legacy 폴더를 재귀 적용하지 않는다.

```powershell
kubectl apply -k C:\aws-msa-backend-terraform\app\msa
kubectl get pods,hpa,ingress -n soldesk
kubectl get pvc -n monitoring
kubectl top nodes
```

ACM 인증서 발급 완료 후 Ingress를 적용한다. `final-app-alb`가 생성되고 HTTPS 리스너가 준비되면 DNS를 연결한다.
첫 Terraform 적용에는 `enable_website_dns = false`를 유지한다. ALB 준비 후 `C:\aws-msa-backend-terraform\terraform\terraform.tfvars`에 `enable_website_dns = true`를 추가하고, 해당 Terraform 폴더에서 비밀번호 환경변수를 전달하여 plan/apply한다.
이 값은 이후에도 true로 유지한다. false로 되돌리면 웹사이트 A 레코드 삭제가 계획된다.
접속 주소는 `https://server.syong.store`이며, ALB 기본 주소로 접속하면 도메인 규칙과 일치하지 않는다.

10. Argo CD 설치 후 GitHub 저장소를 연결한다.

```powershell
helm upgrade --install argocd argo/argo-cd --version 10.10.3 --namespace argocd --values C:\aws-msa-backend-terraform\app\msa\k8s\k8s-argocd\argocd-values.yml --wait --timeout 10m
```

`C:\aws-msa-backend-terraform\app\msa\k8s\k8s-argocd\application.generated.yml`은 `https://github.com/yonginfra/aws-msa-final-project`, `main`, `app/msa`로 생성해 두었다. main 브랜치는 첫 업로드 때 사용할 예정이며 아직 원격에서 확인하지 못했다.
전체 프로젝트 루트를 Git에 올리면 GitPath는 `app/msa`, msa 폴더 자체를 Git 루트로 올리면 `.`이다.
생성 파일을 검토한 다음 적용한다. 비공개 저장소는 Argo CD에 읽기 인증도 별도 등록해야 한다.
HPA가 회원 서비스 복제 수를 바꿔도 Argo CD가 1개로 되돌리지 않도록 예외를 설정했다.

## 관리 화면

아래 port-forward는 각각 별도 PowerShell 창에서 실행한다.

```powershell
kubectl port-forward -n monitoring service/monitoring-grafana 3000:80
kubectl port-forward -n monitoring service/monitoring-kube-prometheus-prometheus 9090:9090
kubectl port-forward -n argocd service/argocd-server 8081:443
```

Grafana: http://localhost:3000, Prometheus: http://localhost:9090, Argo CD: https://localhost:8081.
Grafana 비밀번호는 `monitoring-grafana` Secret의 `admin-password`, Argo CD 초기 비밀번호는 `argocd-initial-admin-secret`의 `password`에 있다.
로컬 Argo CD는 자동 생성 인증서를 사용한다.

## 아직 실제 값이 필요한 항목

- RDS 주소/비밀번호: AWS 생성 후 Secret 스크립트로 입력.
- VPC ID: ALB Controller 설치 시 Terraform output 값 전달.
- GitHub 저장소: 비공개 `yonginfra/aws-msa-final-project`. Argo CD에 저장소 읽기 인증 등록 필요. 토큰/개인 키는 Git에 저장하지 않는다.
- GitHub CI: 저장소 루트의 `.github/workflows/build-push.yml`에 `C:\aws-msa-backend-terraform\app\msa\ci\build-push.yml.template`을 복사. 템플릿은 전체 프로젝트 Git 루트와 main 브랜치 기준이다.
- CI용 GitHub OIDC IAM 역할을 Terraform에서 추가하고 GitHub Actions 변수 `AWS_ROLE_TO_ASSUME`에 역할 ARN 등록. 기존 EKS IRSA OIDC와 별도 구성이다. 저장소 정책에서 Actions의 커밋 쓰기를 허용해야 한다.
- 도메인/ACM: `C:\aws-msa-backend-terraform\terraform\website.tf`에 인증서와 DNS 구성 준비. ALB 생성 후 DNS 연결을 활성화한다.

## 실습에서 확인할 점

- 초기 노드 3개/최대 5개. 설치 작업과 운영 도구까지 동시에 실행하면 CA가 노드를 더 늘릴 수 있다. CPU/메모리/Pending 사유를 실측한다.
- 앱 최소 복제는 1개라 무중단 장애 대응을 보장하지 않는다. 장애 실습 때 필요한 서비스를 2개 이상으로 조정하고 분산을 확인한다.
- EBS는 단일 AZ 볼륨이다. 해당 AZ 노드가 없으면 모니터링 파드가 Pending일 수 있다. 앱 파드 장애 실습과 AZ 장애 실습을 구분한다.
- EBS 3개/총 7Gi와 ALB는 Kubernetes 설치 후 추가 비용이 발생하며 Terraform의 93개 계획에 포함되지 않는다. Prometheus retentionSize는 전체 디스크 사용량 상한을 보장하지 않는다.
- Helm uninstall이 Prometheus/Alertmanager PVC를 자동 삭제하지 않을 수 있다. 종료 시 PVC/EBS를 확인해 정리한다.
- 주문 서비스에 SNS 권한은 연결했지만 주문 생성 시 SNS 이벤트 발행/소비하는 앱 로직은 아직 없다. SNS/SQS 흐름 실습은 CLI 테스트 메시지로 진행한다.
- 프런트엔드 디자인 개선은 요청대로 실제 배포 후 진행한다.
