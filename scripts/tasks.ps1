param(
  [ValidateSet('setup','dev','test','lint','security','package','terraform-fmt','terraform-validate','terraform-plan','terraform-apply','terraform-destroy','smoke-test')]
  [string]$Task = 'test',
  [ValidateSet('dev','staging','prod')][string]$EnvName = 'dev'
)
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
function Invoke-Checked { param([string]$Program, [string[]]$Arguments)
  & $Program @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$Program failed with exit code $LASTEXITCODE" }
}
$taskRoot = "infrastructure/environments/$EnvName"
switch ($Task) {
  'setup' { Invoke-Checked uv @('sync','--locked'); Push-Location apps/web; try { Invoke-Checked npm.cmd @('ci') } finally { Pop-Location } }
  'dev' { Invoke-Checked docker @('compose','up','--build','-d'); Write-Output 'API: http://localhost:8000. In another terminal: cd apps/web; npm run dev (set VITE_MODE=local in apps/web/.env).' }
  'test' { Invoke-Checked uv @('run','pytest'); Push-Location apps/web; try { Invoke-Checked npm.cmd @('test') } finally { Pop-Location } }
  'lint' { Invoke-Checked uv @('run','ruff','check','.'); Invoke-Checked uv @('run','ruff','format','--check','.'); Invoke-Checked uv @('run','mypy','apps','packages','scripts'); Push-Location apps/web; try { Invoke-Checked npm.cmd @('run','check') } finally { Pop-Location } }
  'security' { Invoke-Checked uvx @('--from','checkov==3.2.459','checkov','--config-file','.checkov.yaml'); Invoke-Checked trivy @('fs','--scanners','vuln,secret','--severity','HIGH,CRITICAL','--exit-code','1','.') }
  'package' { Invoke-Checked uv @('run','python','scripts/package.py') }
  'terraform-fmt' { Invoke-Checked terraform @('fmt','-recursive','infrastructure') }
  'terraform-validate' { foreach ($taskDir in @('infrastructure/bootstrap','infrastructure/environments/dev','infrastructure/environments/staging','infrastructure/environments/prod')) { Invoke-Checked terraform @("-chdir=$taskDir",'init','-backend=false','-input=false'); Invoke-Checked terraform @("-chdir=$taskDir",'validate') } }
  'terraform-plan' { if (!(Test-Path "$taskRoot/backend.hcl")) { throw 'Copy backend.hcl.example to backend.hcl and set your bucket first.' }; Invoke-Checked terraform @("-chdir=$taskRoot",'init','-backend-config=backend.hcl'); Invoke-Checked terraform @("-chdir=$taskRoot",'plan','-out=deployment.tfplan') }
  'terraform-apply' { if ((Read-Host "Type APPLY $EnvName to deploy billable AWS resources") -ne "APPLY $EnvName") { throw 'Deployment cancelled' }; Invoke-Checked terraform @("-chdir=$taskRoot",'apply','deployment.tfplan') }
  'terraform-destroy' { if ($EnvName -ne 'dev') { throw 'Automatic teardown is restricted to dev. Follow OPERATIONS.md for other environments.' }; if ((Read-Host 'Type DESTROY dev to delete development infrastructure') -ne 'DESTROY dev') { throw 'Teardown cancelled' }; Invoke-Checked terraform @("-chdir=$taskRoot",'destroy') }
  'smoke-test' { Invoke-Checked uv @('run','python','scripts/smoke.py') }
}
