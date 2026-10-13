# 기본은 로컬 빌드만 수행. AWS 생성 후 -Push를 지정할 때 ECR 업로드
[CmdletBinding()]
param(
    [ValidatePattern('^[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}$')][string]$ImageTag = 'lab-v1',
    [switch]$Push
)
$ErrorActionPreference = 'Stop'
$appRoot = Split-Path $PSScriptRoot -Parent
$registry = '143710973003.dkr.ecr.ap-northeast-2.amazonaws.com'
$services = [ordered]@{
    member = 'member-service'
    product = 'product-service'
    ordering = 'ordering-service'
    apigateway = 'apigateway'
    frontend = 'frontend-service'
}
if ($Push) {
    $account = & aws sts get-caller-identity --query Account --output text
    if ($LASTEXITCODE -ne 0 -or $account.Trim() -ne '143710973003') { throw 'AWS 계정이 프로젝트와 다릅니다.' }
    $token = & aws ecr get-login-password --region ap-northeast-2
    if ($LASTEXITCODE -ne 0) { throw 'ECR 로그인 토큰을 가져오지 못했습니다.' }
    $token | & docker login --username AWS --password-stdin $registry
    $token = $null
    if ($LASTEXITCODE -ne 0) { throw 'Docker ECR 로그인 실패' }
}
foreach ($entry in $services.GetEnumerator()) {
    $localImage = "$($entry.Value):$ImageTag"
    & docker build --platform linux/amd64 -t $localImage (Join-Path $appRoot $entry.Key)
    if ($LASTEXITCODE -ne 0) { throw "$localImage 빌드 실패" }
    if ($Push) {
        $remoteImage = "$registry/$($entry.Value):$ImageTag"
        & docker tag $localImage $remoteImage
        if ($LASTEXITCODE -ne 0) { throw '이미지 태그 실패' }
        & docker push $remoteImage
        if ($LASTEXITCODE -ne 0) { throw "$remoteImage 업로드 실패" }
    }
}
if ($Push) {
    # 5개 업로드가 모두 성공한 경우에만 Git 배포 태그 변경
    $manifest = Join-Path $appRoot 'kustomization.yaml'
    $text = [IO.File]::ReadAllText($manifest)
    $text = [regex]::Replace($text, '(?m)^    newTag: .+$', "    newTag: $ImageTag")
    [IO.File]::WriteAllText($manifest, $text, (New-Object Text.UTF8Encoding($false)))
    Write-Host 'ECR 업로드와 배포 태그 변경 완료. Git 반영은 별도 진행하세요.'
}

