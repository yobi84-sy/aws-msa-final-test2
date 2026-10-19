# 기본은 준비한 규칙 표시만 합니다. -Apply를 명시해야 GitHub main 보호를 변경합니다.
[CmdletBinding()]
param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$rules = Join-Path $PSScriptRoot 'branch-protection.json'
if (-not $Apply) {
    Get-Content -LiteralPath $rules
    Write-Host '미적용: 팀원의 write 권한·요금제·required-ci 실행 이력을 확인한 뒤 -Apply로 적용하세요.'
    return
}
& gh api --method PUT 'repos/yobi84-sy/aws-msa-final-test2/branches/main/protection' --input $rules
if ($LASTEXITCODE -ne 0) { throw 'main 보호 규칙 적용 실패. 권한과 요금제를 확인하세요.' }
Write-Host 'main 보호 설정 완료. 실패 PR·승인 전 병합 차단을 실제로 확인하세요.'
