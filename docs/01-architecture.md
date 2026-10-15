# 프로젝트 구성

앱을 크게 만드는 것보다는 AWS와 Kubernetes의 배포·운영 흐름을 확인하는 데 집중했다. 앱은 회원·상품·주문 기능이 있는 간단한 쇼핑몰로 구성했다.

## 전체 구성도

![AWS EKS 프로젝트 구성도](images/architecture.png)

[확대 가능한 SVG 원본](images/architecture.svg)

## 주요 구성

| 구분 | 구성 |
| --- | --- |
| 네트워크 | 서울 리전의 2개 가용 영역, 퍼블릭·프라이빗·DB 서브넷 |
| 외부 접속 | 공유 ALB, Route 53, ACM 인증서 |
| 앱 실행 | EKS, 서비스별 Docker 이미지, ECR |
| 데이터 저장 | RDS MySQL, 상품 이미지용 S3 |
| 운영 도구 | Argo CD, Prometheus, Grafana, Alertmanager |

ALB 하나에서 도메인으로 웹사이트·Grafana·Argo CD를 구분했다. 실습 비용을 고려해 NAT Gateway는 하나, RDS는 Single-AZ로 구성했다.

## 코드는 어떻게 나눴는지

- `terraform`: VPC·EKS·RDS·IAM 등 AWS 인프라
- `terraform-k8s`: EKS 내부 컨트롤러와 운영 도구 설치
- `app/msa`: 앱 코드와 배포 매니페스트

EKS가 먼저 있어야 내부 도구를 설치할 수 있어서 두 Terraform 구성을 분리했다. 앱 변경은 Argo CD가 Git을 기준으로 반영하도록 했다.

---

[프로젝트 홈](../README.md) · [다음: 배포 자동화](02-deployment.md)
