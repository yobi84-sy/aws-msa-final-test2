# 이전 검증 이미지로 복구하는 PR

롤백은 Argo CD가 추적하는 Git 선언을 복구하는 변경입니다. `kubectl rollout undo`만 실행하면 Git의 오류 버전으로 다시 동기화될 수 있습니다. 현재는 digest와 release.json을 함께 복구합니다. 이전 태그 직접 수정·main 직접 push 방식은 [과거 기록](archive/2026-11-04/ROLLBACK.md)입니다.

## 실행 전 확인

1. 현재 revision·장애 증상·이미지 digest를 기록합니다. 앱 기능 오류와 DB/인프라 장애를 구분합니다.
2. 이전에 정상 검증한 **origin/main의 전체 40자리 SHA**와 해당 release.json을 선택합니다.
3. 이전 코드가 현재 DB 스키마·외부 API와 호환되는지 검토합니다. 이 절차는 DB·인프라를 자동 복구하지 않습니다.
4. 작업 디렉터리는 깨끗해야 하며 ECR의 다섯 이미지가 남아 있어야 합니다. 전체 삭제 후에는 과거 digest를 바로 실행할 수 없을 수 있습니다.

## 복구 제안

[스크립트](../scripts/ops/rollback_release.py)의 현재 옵션을 먼저 확인합니다.

```powershell
python scripts/ops/rollback_release.py --help
```

이전 release의 다섯 이미지 존재를 검사한 뒤 별도 브랜치에서 Kustomize 이미지와 release.json을 복구해 PR을 제안합니다. 검토·승인·검사 후 병합하고 Argo 동기화, 새 파드 준비, 실제 사용자 기능과 데이터를 확인합니다. 완료 전에 단순히 rollout 성공만 보고 복구를 선언하지 않습니다.

2026-11-02 #25에서는 이전 V1 digest로 복구 후 동일 상품·재고·이미지와 상세 동작을 확인했습니다. 이어 #26/#28에서 원인을 수정하고 회귀 검사를 포함한 V3를 배포했습니다. [배포 이력](RELEASES.md)
