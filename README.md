# AWS · EKS 서비스 운영 프로젝트

Terraform으로 AWS 인프라를 구성하고, GitHub Actions와 Argo CD로 앱을 배포한 운영 실습 프로젝트입니다.

앱 기능 자체보다는 **배포 자동화, 모니터링, 자동 확장, 장애 복구**를 직접 확인하는 데 집중했습니다.

![AWS EKS 프로젝트 구성도](docs/images/architecture.png)

## 프로젝트 문서

전체 내용을 한 페이지에 넣기보다 주제별로 나눴습니다. 처음 보는 기술도 따라갈 수 있도록 **역할 → 사용한 이유 → 실습 결과** 순서로 설명했습니다.

| 페이지 | 내용 |
| --- | --- |
| [프로젝트 구성](docs/01-architecture.md) | 구성도, 주요 서비스, Terraform 폴더 분리 |
| [배포 자동화](docs/02-deployment.md) | GitHub Actions → ECR → Argo CD → EKS |
| [모니터링과 실습 결과](docs/03-monitoring-and-tests.md) | 지표·이메일 알림, 자동 확장, 메시징 검증 |
| [문제 해결 기록](docs/04-troubleshooting.md) | Grafana 503, 관리자 로그인, Terraform 오류 |
| [프로젝트 회고](docs/05-retrospective.md) | 배운 점과 실습 범위 |
| [개선 적용·검증](docs/10-live-validation.md) | 원격 state, 테스트, 복원, 가용성 개선과 코드 리뷰 |

[배포 이력·이미지 태그](docs/RELEASES.md) · [이전 버전으로 롤백](docs/ROLLBACK.md)

## 사용 기술

Helm·Kustomize는 [배포 자동화](docs/02-deployment.md), EBS는 [프로젝트 구성](docs/01-architecture.md), SNS·SQS·CloudWatch·CloudTrail은 [모니터링과 실습 결과](docs/03-monitoring-and-tests.md)에서 쉽게 풀어 설명했습니다.

- **인프라:** Terraform · VPC · EKS · IAM · ALB · Route 53 · ACM
- **배포:** Docker · ECR · GitHub Actions · Argo CD · Helm · Kustomize
- **데이터·운영:** RDS · S3 · EBS · Prometheus · Grafana · SNS · SQS · CloudWatch · CloudTrail

## 저장소 구조

```text
.
├── terraform-state-bootstrap/ # 따로 보관하는 state용 S3 버킷
├── terraform/          # AWS 인프라
├── terraform-k8s/      # EKS 내부 운영 도구
├── app/msa/            # 앱 코드와 배포 매니페스트
├── .github/workflows/  # 변경 서비스 테스트·이미지 빌드·태그 갱신
├── scripts/            # 빌드 대상 선택·잔여 자원·복원·접속 점검
└── docs/               # 구성·실습·문제 해결 기록
```

## 확인한 결과

- GitHub 코드 변경부터 실제 홈페이지 반영까지 배포 흐름 확인
- 파드 재생성·재배치와 파드·노드 수 변화 확인
- 운영 경보와 주문 알림 이메일 수신
- SNS → SQS → DLQ 전달 및 CloudWatch 경보 확인
- CloudTrail 작업 이력과 S3 로그 확인
- S3 원격 state 저장과 동시 작업 잠금 확인
- EKS 관리 로그 수집과 별도 RDS 복원 데이터 확인
- 프런트엔드 2개·PDB·종료 대기 설정 후 파드 교체 중 접속 확인
- Terraform 세 구성의 validate 성공과 plan에서 No changes 확인

웹사이트·Grafana·Argo CD는 공유 ALB와 개별 도메인으로 연결했습니다. 실습 인프라를 삭제한 동안에는 접속되지 않습니다.

프런트엔드는 두 파드로 구성했고, 일부 백엔드·운영 도구는 단일 파드이며 RDS는 Single-AZ입니다. 모든 장애에서 무중단을 보장하는 구조는 아닙니다.

## 이번에 개선한 내용

| 개선 | 사용한 이유 |
| --- | --- |
| S3 원격 state·잠금 | Terraform이 관리하는 자원 정보를 함께 사용하고 동시 수정을 방지 |
| 변경 서비스만 테스트·빌드 | 관련 없는 이미지까지 다시 만드는 작업 감소 |
| EKS 관리 로그 | Kubernetes API 요청과 인증·감사 기록 확인 |
| 상태 점검 분리 | 시작 대기·트래픽 수신 준비·프로세스 이상을 구분 |
| 프런트엔드 2개·PDB | 노드 점검 중 최소 한 파드를 유지하도록 구성 |
| RDS 복원·운영 스크립트 | 백업 데이터 복원, 잔여 자원 조회, HTTPS 접속을 직접 확인 |

테스트 실패 시 이미지 게시를 중단하며, 배포 후에는 Actions 성공과 별도로 Argo CD 상태와 실제 접속을 확인합니다.

## 실행 안내

[PowerShell 실행 순서](docs/06-monday-runbook.md) · [state 설명](docs/07-terraform-state.md) · [RDS 복원 실습](docs/08-rds-restore-lab.md)

state 버킷을 먼저 준비하고 **AWS 인프라 → EKS 내부 구성 → 앱 배포 → DNS 연결** 순서로 진행합니다. 삭제는 EKS 내부 구성부터 진행하며, state 버킷은 따로 보관합니다.

GitHub Actions의 이미지 게시 대상은 main입니다. 기본 Argo CD 대상도 main이며, 별도 실습에서는 `github_revision`으로 검증 브랜치를 지정할 수 있습니다. 실제 적용 결과와 확인하지 않은 범위는 [검증 기록](docs/10-live-validation.md)에 구분했습니다.

**브랜치:** main은 검증한 개선 버전, test는 개선 전 main 보관용입니다. 새 수정은 최신 main에서 작업 브랜치를 만들어 진행합니다. 이전 test 코드를 현재 S3 state 환경에 그대로 적용하지 않습니다.
