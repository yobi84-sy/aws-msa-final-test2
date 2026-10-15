# 이전 배포로 돌아가기

Argo CD가 Git을 기준으로 자동 동기화하므로, 이미지 롤백도 Git에 남긴다.

## 관리자 대시보드 이전 버전

4차 관리자 대시보드 직전의 앱 이미지 태그:

```text
58ab067dd239160afc60941cf14aee5830ca5840
```

`app/msa/kustomization.yaml`의 관련 서비스 `newTag`를 위 값으로 바꾸고 commit/push한다. 이번에는 화면·회원 서비스·Gateway를 함께 변경했으므로 이전 앱 배포 전체로 돌아가려면 다섯 이미지의 `newTag`를 모두 이 태그로 맞춘다.

```powershell
Set-Location 'C:\aws-msa-backend-terraform'
git diff -- app/msa/kustomization.yaml
git add app/msa/kustomization.yaml
git commit -m "Roll back app images to the previous release"
git push origin main
```

태그만 변경하면 이미지를 다시 빌드하지 않고 Argo CD가 기존 ECR 이미지로 배포한다. 배포 완료 후 파드와 서비스 접속을 확인한다.

```powershell
kubectl get applications -n argocd
kubectl get pods -n soldesk
```

`kubectl rollout undo`만 실행하면 Argo CD가 Git에 적힌 버전으로 되돌릴 수 있다. 유지할 변경은 Git에도 반영한다.

이번 대시보드는 DB 구조를 바꾸지 않았다. 향후 DB 스키마나 설정도 함께 바꾼 배포는 이미지 외에 관련 변경의 호환성도 확인한다. 이전 배포 커밋 전체를 되돌릴 필요가 있으면 해당 변경을 `git revert`하는 방법을 사용한다.

[프로젝트 홈](../README.md)
