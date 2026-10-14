# 프론트엔드 화면 변경과 롤링 업데이트 실습

변경 전에는 Soldesk Mall 화면, 변경 후에는 크림색/초록색 SYONG STORE 화면을 확인한다. 화면 하단의 EDITION 02로 새 버전을 구분할 수 있다.

## 변경 전 기록 (2026-10-14)

- 배포 이미지: `143710973003.dkr.ecr.ap-northeast-2.amazonaws.com/frontend-service:fb1b6d340f24ccaeaca6ae1bd05e1ed020a6a21b`
- ECR에 이 태그의 이미지가 남아 있는 것을 확인했다.
- 당시 Git main: `2bb2213` (위 이미지 태그를 기록한 봇 커밋).
- 실제 파드와 노드는 `kubectl get pods -n soldesk -l app=frontend -o wide`로 다시 확인한다.

## 교체 설정

`C:\aws-msa-backend-terraform\app\msa\frontend\k8s\depl_svc.yml`:

```yaml
replicas: 1
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0
minReadySeconds: 10
progressDeadlineSeconds: 300
```

새 파드를 하나 더 만들고 readiness probe가 통과한 상태로 10초 유지된 뒤 기존 파드를 종료한다. 배치 공간이 부족하면 새 파드가 Pending으로 남고 기존 파드는 유지된다. progressDeadlineSeconds는 진행 실패를 보고하는 기준이며 자동 롤백 타이머가 아니다.

이 설정만으로 ALB의 모든 요청에 대한 무중단을 보장하지는 않는다. 파드 준비 상태와 ALB 대상 상태 반영에는 차이가 있으므로 실제 HTTP 응답도 확인한다.

## 관찰을 시작한 뒤 push

PowerShell 창 1:

```powershell
kubectl get pods -n soldesk -l app=frontend -o wide --watch
```

PowerShell 창 2:

```powershell
kubectl get rs -n soldesk -l app=frontend --watch
```

PowerShell 창 3:

```powershell
cd C:\aws-msa-backend-terraform
git status
git push origin main
```

현재 워크플로는 프론트엔드를 수정해도 서비스 이미지 5개를 모두 빌드하고 태그를 갱신한다. 따라서 이번 실행에서 다른 서비스도 새 이미지로 교체될 수 있다. frontend만 관찰하더라도 전체 앱 상태를 함께 확인한다.

GitHub Actions 성공 후 봇이 kustomization.yaml을 갱신하고 Argo CD가 반영한다. 새 프론트엔드 파드가 생성되기 시작한 것을 확인한 뒤:

```powershell
kubectl rollout status deployment/frontend-depl -n soldesk --timeout=300s
kubectl get applications -n argocd
kubectl get pods -n soldesk
kubectl get deployment frontend-depl -n soldesk -o jsonpath='{.spec.template.spec.containers[0].image}'
```

확인 항목: 새 ReplicaSet 생성, 새 파드 Ready, 잠시 기존/신규 파드 공존, 기존 파드 종료, 최종 파드 1개, Argo Synced/Healthy, 새 화면 및 로그인/상품 기능. 배포 전 실행한 rollout status는 이전 버전의 완료만 보여줄 수 있다.

브라우저에서 https://server.syong.store 를 확인한다. 배포 도중에는 두 버전이 번갈아 보일 수 있다. 배포 완료 뒤 캐시가 남으면 Ctrl+Shift+R로 새로고침한다.

## 이전 프론트엔드 이미지로 롤백

Argo CD가 Git을 기준으로 자동 동기화하므로 Git의 태그를 되돌린다.

```powershell
cd C:\aws-msa-backend-terraform
git pull --ff-only origin main
```

`C:\aws-msa-backend-terraform\app\msa\kustomization.yaml`에서 frontend-service 항목의 newTag만 아래 값으로 수정한다. 다른 서비스 태그는 유지한다.

```yaml
- name: 143710973003.dkr.ecr.ap-northeast-2.amazonaws.com/frontend-service
  newTag: fb1b6d340f24ccaeaca6ae1bd05e1ed020a6a21b
```

```powershell
git add app/msa/kustomization.yaml
git commit -m "Roll back frontend to the previous image"
git push origin main
```

이 경로만 바꾸는 커밋은 현재 이미지 빌드 워크플로의 push 조건에 해당하지 않아 이미지를 다시 빌드하지 않는다. Argo CD가 기존 ECR 이미지로 교체한 뒤 옛 화면이 보이는지 확인한다. 다시 새 화면을 적용하려면 새 이미지 태그로 같은 절차를 진행한다.

## 로컬 확인 범위

Docker 이미지 빌드/NGINX 설정, JS 구문, Kustomize 렌더링, 데스크톱/휴대폰 폭의 메인·로그인·회원가입·상품 상세 표시를 확인했다. 로컬 미리보기의 예제 상품은 별도 컨테이너 설정에만 있으며 Git 소스와 배포 이미지에 포함하지 않는다. 실제 회원가입/상품등록/주문 API의 동작은 배포 후 테스트 계정으로 확인한다.
