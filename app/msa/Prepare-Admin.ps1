# 관리자 비밀번호를 Git에 저장하지 않고 Kubernetes Secret으로 준비한다.
$ErrorActionPreference = 'Stop'
$context = kubectl config current-context
if ($LASTEXITCODE -ne 0 -or $context -ne 'arn:aws:eks:ap-northeast-2:021158485482:cluster/Final-eks') {
    throw 'Final-eks 클러스터에 연결한 PowerShell에서 실행하세요.'
}
$securePassword = Read-Host '새 관리자 비밀번호 (12~64자, 입력은 표시되지 않음)' -AsSecureString
$pointer = [IntPtr]::Zero
try {
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
    $passwordText = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    if ($passwordText.Length -lt 12 -or $passwordText.Length -gt 64) {
        throw '비밀번호는 12~64자로 입력하세요.'
    }
    # 개인 이메일은 주문 SNS 구독을 사용하므로 관리자 계정에는 별도 주소를 사용한다.
    $secret = @{
        apiVersion = 'v1'; kind = 'Secret'
        metadata = @{ name = 'final-admin-config'; namespace = 'soldesk' }
        type = 'Opaque'
        data = @{
            'admin-password' = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($passwordText))
            'admin-email' = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes('admin@sy84.store'))
        }
    }
    $secret | ConvertTo-Json -Depth 5 -Compress | kubectl apply --server-side --field-manager=final-admin-setup -f -
    if ($LASTEXITCODE -ne 0) { throw 'Secret 설정에 실패했습니다.' }
    Write-Host '관리자 Secret 준비 완료. 새 앱 배포 후 admin / 방금 입력한 비밀번호로 로그인하세요.'
    Write-Host '이미 배포한 뒤 비밀번호를 바꿨다면: kubectl rollout restart deployment/member-depl -n soldesk'
} finally {
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    $passwordText = $null
    $secret = $null
    $securePassword.Dispose()
}
