# 모니터링과 실습 결과

Prometheus와 Grafana만 쓰면 되는 줄 알았는데, 실제로 구성해보니 AWS 서비스 지표와 Kubernetes 지표는 나눠서 보는 게 이해하기 편했다.

## 도구별 역할

| 도구 | 이번 프로젝트에서 사용한 용도 |
| --- | --- |
| Prometheus·Grafana | 노드·파드·서비스 상태 수집과 대시보드 |
| Alertmanager | Kubernetes 알림을 SNS로 전달 |
| CloudWatch | RDS와 SQS 지표를 기준으로 경보 발생 |
| SNS | 운영 경보·노드 변경·주문 알림을 이메일로 전달 |
| SQS·DLQ | 메시지 수신과 반복 처리 실패 메시지 분리 |
| CloudTrail | AWS 관리 API 작업의 성공·실패 이력 확인 |

## 확인한 실습

| 실습 | 결과 |
| --- | --- |
| 파드 복구 | 기존 파드 종료 후 새 파드 생성과 서비스 접속 확인 |
| 자동 확장 | 부하에 따른 회원 파드 증가·감소, 노드 수 변화와 알림 확인 |
| 배포 변경 | GitHub Actions와 Argo CD를 거쳐 홈페이지 변경 확인 |
| Grafana 재배치 | 다른 노드로 이동한 뒤 기존 저장소를 유지하며 복구 |
| SNS·SQS·DLQ | 테스트 메시지 수신, 반복 수신 후 DLQ 이동, 경보 메일 확인 |
| CloudTrail | RDS 생성 실패·성공 이력과 S3 로그 확인 |
| 앱 기능 | 관리자 접근 제한, 장바구니, 수량 주문, 운영자 주문 메일 확인 |
| 최종 설정 점검 | 두 Terraform 구성 모두 validate 성공, plan은 No changes |

HPA는 파드 수를, Cluster Autoscaler는 노드 수를 조절한다. 노드 증가 메일만 보고 원인을 단정하지 않고 Pending 사유와 로그도 함께 확인했다.

SQS 실습은 테스트 메시지로 진행했다. 실제 앱의 주문 메일은 기존 운영 SNS로 직접 보내며, SQS 메시지 소비자는 구현하지 않았다.

실습이 끝난 테스트 메시지는 삭제하고 경보가 정상으로 돌아오는 것까지 확인했다.

---

[프로젝트 홈](../README.md) · [이전: 배포 자동화](02-deployment.md) · [다음: 문제 해결 기록](04-troubleshooting.md)
