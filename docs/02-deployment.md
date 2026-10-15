# 배포 자동화

처음에는 이미지를 직접 올려서 배포했지만, 이후에는 GitHub에 코드를 올리면 EKS까지 반영되도록 연결했다.

## 배포 흐름

```text
코드 변경 → GitHub push → GitHub Actions
  → 이미지 빌드·ECR 업로드
  → Git의 이미지 태그 갱신 → Argo CD → EKS 배포
```

이미지에는 Git 커밋별 태그를 사용했다. 어떤 코드로 만든 이미지인지 확인하고 이전 버전과 비교하기 쉽도록 하기 위해서다.

GitHub Actions는 OIDC로 AWS IAM 역할을 사용한다. 앱 파드도 ServiceAccount에 연결한 IAM 역할로 필요한 S3·SNS 작업을 수행한다.

## 직접 확인한 내용

프런트엔드를 수정한 뒤 빌드 성공, 이미지 태그 갱신, Argo CD 동기화, 실제 홈페이지 변경까지 확인했다. 배포 중 파드가 교체되는 것도 살펴봤다.

관리자 화면과 장바구니를 추가했을 때도 같은 흐름으로 배포했다. 운영 도구는 Terraform으로 관리하고, 앱은 Git을 통해 배포하는 식으로 역할을 나눴다.

## 다시 구축할 때의 순서

1. AWS 인프라 생성
2. kubeconfig 연결과 ECR 이미지 준비
3. EKS 내부 도구·Secret 준비 후 앱 배포
4. 공유 ALB 생성 확인 후 DNS 연결

처음에는 ALB가 없으므로 DNS 활성화 설정을 확인해야 한다. 배포 방식은 현재 `terraform-k8s` 구성을 기준으로 하며, 동일한 도구를 수동 Helm 명령으로 중복 설치하지 않는다.

앱 기능의 설정 절차는 [앱 기능 안내](../app/msa/APP-FEATURES.md)에 정리했다.

---

[프로젝트 홈](../README.md) · [이전: 프로젝트 구성](01-architecture.md) · [다음: 모니터링과 실습 결과](03-monitoring-and-tests.md)
