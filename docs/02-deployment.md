# 테스트한 이미지를 승인 후 GitOps로 배포하기

현재 기준은 main과 digest 기반 배포 PR입니다. 예전 `test` 브랜치나 이미지 태그를 main에 직접 갱신하던 기록은 [과거 문서](README.md)입니다.

## 소스 검사와 이미지 게시

[build-push.yml](../.github/workflows/build-push.yml)은 변경 서비스를 선택하고 자동화 단위 검사·설정 검사·Windows 실행 검사를 수행합니다. 서비스 검사와 Docker 빌드가 통과한 이미지 산출물을 보관한 후, 게시 단계에서 동일 산출물을 ECR에 올립니다. 게시를 위한 별도 미검증 재빌드를 하지 않습니다.

[test-service.sh](../scripts/ci/test-service.sh)는 Member·Product·Ordering의 지정된 테스트, Gateway 테스트, 프런트엔드 Node 검사를 실행합니다. 모든 Java 테스트와 실제 RDS 통합 검사를 무조건 실행하는 구성은 아닙니다. Python 자동화 검사의 다수도 모의 실행입니다.

PR 검사는 이미지를 게시하지 않습니다. main 게시 역시 `ENABLE_IMAGE_PUBLISH` 또는 명시적 dispatch 입력 등 워크플로 조건을 따릅니다. push 한 번이 인프라 설치와 앱 운영 배포를 항상 시작하는 구조는 아닙니다.

## 이미지 배포 PR과 Argo CD

OIDC로 ECR 게시 권한을 얻고 서비스별 digest를 고정합니다. 워크플로는 main을 직접 수정하는 대신 release 브랜치에서 다음 파일을 바꾸는 PR을 만듭니다.

- [app/msa/kustomization.yaml](../app/msa/kustomization.yaml): 실행할 이미지 digest
- [deploy/release.json](../deploy/release.json): 서비스별 소스 SHA·digest·워크플로 출처

검사·동료 검토 후 병합하면 Argo CD가 Git의 선언을 읽어 EKS를 동기화하고 노드가 ECR 이미지를 받습니다. **ECR→Argo CD가 이미지 전달 경로인 것은 아닙니다.** 승인 정책 코드는 [review-policy.yml](../.github/workflows/review-policy.yml)에 있으며 저장소 보호 설정도 유지해야 합니다. 다른 저장소로 복사한다고 GitHub의 보호 규칙까지 자동으로 생기지는 않습니다.

최초 설치는 고정된 release commit을 사용하고, 승인된 초기 배포 PR을 확인한 뒤 `Install-Lab.ps1 -Execute -PromoteMain` 경로로 main 추적에 전환합니다. 실제 실행 전 [설치 가이드](15-one-command-lab.md)의 체크포인트를 확인합니다.

## VPC CodeBuild의 배포 후 검사

[deploy-check.yml](../.github/workflows/deploy-check.yml)은 배포 선언 병합 또는 dispatch를 받아 `ENABLE_DEPLOY_CHECKS` 조건으로 실행됩니다. GitHub OIDC→검증 소스 ZIP S3→VPC CodeBuild 순서입니다. CodeBuild는 사설 EKS API에 접근할 수 있도록 기존 프라이빗 서브넷을 사용합니다.

검사 대상은 revision·이미지·가용성·TLS·HTML·상품 API입니다. EKS 권한은 soldesk Deployment와 지정 Argo Application의 조회 중심으로 제한하며 Secret 읽기·배포 변경 권한을 주지 않습니다. 정상 검증과 의도적으로 잘못된 revision 실패는 [10월 실제 기록](17-validation-20261021.md)에서 확인합니다.

이 검사를 통과해도 모든 사용자 동작이 정상인 것은 아닙니다. V2의 상품 상세 오류는 기존 기본 검사를 통과했으므로 V3에서 카드→상세 회귀 검사를 추가했습니다. [실제 흐름과 PR](RELEASES.md)

## 롤백과 다음 버전

복구도 Git에 선언하고 검토하는 변경입니다. [rollback_release.py](../scripts/ops/rollback_release.py)는 이전 main의 release에서 이미지 digest를 가져와 복구 PR을 제안합니다. DB·Terraform은 되돌리지 않습니다. 스키마·외부 API 호환성과 ECR 이미지 존재를 먼저 확인합니다. [절차](ROLLBACK.md)

애플리케이션 자동 배포와 Terraform 인프라 적용은 별도입니다. 이 문서 최신화 PR은 앱·Terraform 설정을 바꾸지 않으며 AWS 배포 시험도 수행하지 않습니다.
