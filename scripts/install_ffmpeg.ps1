# FFmpeg 자동 설치 및 경로 설정 스크립트 (Windows용)
$installPath = "C:\ffmpeg"
$zipPath = "$env:TEMP\ffmpeg.zip"
# 최신 GPL 빌드 다운로드 주소
$url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

Write-Host "--------------------------------------------------" -ForegroundColor Magenta
Write-Host " AMEVA FFmpeg 자동 설치 도구" -ForegroundColor Magenta
Write-Host "--------------------------------------------------" -ForegroundColor Magenta

if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "[INFO] FFmpeg가 이미 설치되어 있습니다." -ForegroundColor Green
    exit
}

try {
    Write-Host "[1/4] FFmpeg 다운로드 중 (약 100MB)..." -ForegroundColor Cyan
    Invoke-WebRequest -Uri $url -OutFile $zipPath

    Write-Host "[2/4] 압축 해제 중 ($installPath)..." -ForegroundColor Cyan
    if (Test-Path $installPath) { 
        Write-Host "기존 폴더 삭제 중..." -ForegroundColor Gray
        Remove-Item -Recurse -Force $installPath 
    }
    New-Item -ItemType Directory -Path $installPath | Out-Null
    Expand-Archive -Path $zipPath -DestinationPath "$installPath\_temp"

    # 폴더 구조 정리 (추출된 하위 폴더의 내용물을 C:\ffmpeg로 이동)
    $innerDir = Get-ChildItem "$installPath\_temp" | Where-Object { $_.PSIsContainer } | Select-Object -First 1
    Move-Item "$($innerDir.FullName)\*" $installPath
    Remove-Item "$installPath\_temp" -Recurse -Force

    Write-Host "[3/4] 시스템 환경 변수(Path) 등록 중..." -ForegroundColor Cyan
    $binPath = "$installPath\bin"
    # 현재 세션 및 시스템 영구 환경 변수 등록
    $oldPath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    if (-not $oldPath.Contains($binPath)) {
        [Environment]::SetEnvironmentVariable("Path", $oldPath + ";$binPath", "Machine")
        $env:Path += ";$binPath"
    }

    Write-Host "[4/4] 임시 파일 삭제 중..." -ForegroundColor Cyan
    Remove-Item $zipPath

    Write-Host "--------------------------------------------------" -ForegroundColor Magenta
    Write-Host "FFmpeg 설치 성공! (위치: $binPath)" -ForegroundColor Green
    Write-Host "현재 터미널을 닫고 새로 열어야 변경 사항이 완전히 적용됩니다." -ForegroundColor Yellow
    Write-Host "--------------------------------------------------" -ForegroundColor Magenta
}
catch {
    Write-Host "[ERROR] 설치 중 오류가 발생했습니다: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "관리자 권한으로 실행했는지 확인해 주세요." -ForegroundColor Yellow
}
