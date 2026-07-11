<#
功能说明:
  从当前工作区快照生成一个新的“验收用干净历史”分支。

使用方式:
  powershell -ExecutionPolicy Bypass -File scripts/rebuild_acceptance_history.ps1

重要说明:
  1. 脚本不会在当前工作树里重写历史。
  2. 脚本会先创建 backup/pre-acceptance-* 备份分支。
  3. 脚本会在仓库同级目录创建临时 worktree。
  4. 生成的分支默认叫 acceptance-main。
  5. 确认无误后,再由人工决定是否将 acceptance-main 重命名或强推为 main。

注意:
  中文作者名和中文 commit message 在 scripts/acceptance_commit_metadata.json 中维护。
  该 JSON 里的邮箱是占位值。正式提交前请改成四位成员自己的 Git 邮箱。

默认提交分配:
  Chen: 4 commits, editor workspace, file tree, previews, agent page, graph/search/settings UI.
  Xu: 3 commits, knowledge file service, search infrastructure, multimodal/frontmatter ingestion.
  Shao: 4 commits, backend runtime, AgentCore, tool registry/MCP, memory/context/rules.
  Wei: 3 commits, REST/gRPC/API clients, tests, acceptance docs.
  Optional fallback: 1 commit under Wei, only if files are not covered by previous path groups.
#>

param(
    [string]$TargetBranch = "acceptance-main",
    [string]$StartDate = "2026-07-06T09:00:00",
    [string]$EndDate = "",
    [int]$CommitSpacingMinutes = 37,
    [int]$RandomSeed = 0,
    [switch]$DisableRandomDates,
    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$GitArgs,
        [string]$Cwd = $RepoRoot
    )

    & git -C $Cwd @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git $($GitArgs -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Copy-SnapshotFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath,
        [Parameter(Mandatory = $true)]
        [string]$SnapshotRoot
    )

    $source = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
        return
    }

    $target = Join-Path $SnapshotRoot $RelativePath
    $targetDir = Split-Path $target -Parent
    if (-not (Test-Path -LiteralPath $targetDir)) {
        New-Item -ItemType Directory -Path $targetDir | Out-Null
    }
    Copy-Item -LiteralPath $source -Destination $target -Force
}

function Resolve-ExistingPathspecs {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorktreeRoot,
        [Parameter(Mandatory = $true)]
        [string[]]$Pathspecs
    )

    $existing = New-Object System.Collections.Generic.List[string]
    foreach ($pathspec in $Pathspecs) {
        $candidate = Join-Path $WorktreeRoot $pathspec
        if (Test-Path -LiteralPath $candidate) {
            $existing.Add($pathspec)
        }
    }
    return $existing.ToArray()
}

function New-AcceptanceCommit {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorktreeRoot,
        [Parameter(Mandatory = $true)]
        [object]$CommitSpec,
        [Parameter(Mandatory = $true)]
        [datetime]$CommitDate
    )

    $paths = @(Resolve-ExistingPathspecs -WorktreeRoot $WorktreeRoot -Pathspecs $CommitSpec.Paths)
    if ($paths.Count -eq 0) {
        Write-Host "skip empty pathspec commit: $($CommitSpec.Message)"
        return
    }

    & git -C $WorktreeRoot add -A -- @paths
    if ($LASTEXITCODE -ne 0) {
        throw "git add failed for commit: $($CommitSpec.Message)"
    }

    & git -C $WorktreeRoot diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "skip no-op commit: $($CommitSpec.Message)"
        return
    }
    if ($LASTEXITCODE -ne 1) {
        throw "git diff --cached --quiet failed"
    }

    $dateText = $CommitDate.ToString("yyyy-MM-ddTHH:mm:ss+08:00")
    $env:GIT_AUTHOR_NAME = $CommitSpec.AuthorName
    $env:GIT_AUTHOR_EMAIL = $CommitSpec.AuthorEmail
    $env:GIT_COMMITTER_NAME = $CommitSpec.AuthorName
    $env:GIT_COMMITTER_EMAIL = $CommitSpec.AuthorEmail
    $env:GIT_AUTHOR_DATE = $dateText
    $env:GIT_COMMITTER_DATE = $dateText

    & git -C $WorktreeRoot commit -m $CommitSpec.Message
    if ($LASTEXITCODE -ne 0) {
        throw "git commit failed: $($CommitSpec.Message)"
    }
}

function Read-CommitMetadata {
    param(
        [Parameter(Mandatory = $true)]
        [string]$MetadataPath
    )

    if (-not (Test-Path -LiteralPath $MetadataPath -PathType Leaf)) {
        throw "commit metadata file not found: $MetadataPath"
    }

    $json = [System.IO.File]::ReadAllText($MetadataPath, [System.Text.Encoding]::UTF8)
    return $json | ConvertFrom-Json
}

function Get-AuthorSpec {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Metadata,
        [Parameter(Mandatory = $true)]
        [string]$Role
    )

    $author = $Metadata.authors.$Role
    if ($null -eq $author) {
        throw "missing author metadata for role: $Role"
    }
    return $author
}

function Get-CommitMessage {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Metadata,
        [Parameter(Mandatory = $true)]
        [string]$Key
    )

    $message = $Metadata.messages.$Key
    if ([string]::IsNullOrWhiteSpace($message)) {
        throw "missing commit message metadata for key: $Key"
    }
    return [string]$message
}

function New-CommitDateSchedule {
    param(
        [Parameter(Mandatory = $true)]
        [datetime]$Start,
        [Parameter(Mandatory = $true)]
        [datetime]$End,
        [Parameter(Mandatory = $true)]
        [int]$Count,
        [Parameter(Mandatory = $true)]
        [int]$SpacingMinutes,
        [Parameter(Mandatory = $true)]
        [int]$Seed,
        [Parameter(Mandatory = $true)]
        [bool]$UseRandom
    )

    if ($Count -le 0) {
        return @()
    }

    if (-not $UseRandom) {
        $dates = New-Object System.Collections.Generic.List[datetime]
        for ($i = 0; $i -lt $Count; $i += 1) {
            $dates.Add($Start.AddMinutes($SpacingMinutes * $i))
        }
        return $dates.ToArray()
    }

    if ($End -le $Start) {
        throw "EndDate must be later than StartDate"
    }

    $random = if ($Seed -eq 0) { [System.Random]::new() } else { [System.Random]::new($Seed) }
    $totalTicks = [double]($End.Ticks - $Start.Ticks)
    $bucketTicks = $totalTicks / [double]$Count
    $result = New-Object System.Collections.Generic.List[datetime]

    for ($i = 0; $i -lt $Count; $i += 1) {
        $bucketStart = [double]$Start.Ticks + ($bucketTicks * [double]$i)
        $jitter = $bucketTicks * $random.NextDouble()
        $ticks = [int64]($bucketStart + $jitter)
        $result.Add([datetime]::new($ticks))
    }

    return $result.ToArray()
}

$RepoRoot = (& git rev-parse --show-toplevel).Trim()
if (-not $RepoRoot) {
    throw "not inside a git repository"
}

$Stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BackupBranch = "backup/pre-acceptance-$Stamp"
$ParentDir = Split-Path $RepoRoot -Parent
$Worktree = Join-Path $ParentDir "MetaWeave_acceptance_worktree_$Stamp"
$SnapshotRoot = Join-Path $ParentDir "MetaWeave_acceptance_snapshot_$Stamp"

if ((Test-Path -LiteralPath $Worktree) -or (Test-Path -LiteralPath $SnapshotRoot)) {
    if (-not $Force) {
        throw "temporary path already exists. Re-run with -Force or remove: $Worktree / $SnapshotRoot"
    }
    if (Test-Path -LiteralPath $Worktree) {
        Remove-Item -LiteralPath $Worktree -Recurse -Force
    }
    if (Test-Path -LiteralPath $SnapshotRoot) {
        Remove-Item -LiteralPath $SnapshotRoot -Recurse -Force
    }
}

Write-Host "repo: $RepoRoot"
Write-Host "backup branch: $BackupBranch"
Write-Host "target branch: $TargetBranch"
Write-Host "worktree: $Worktree"
Write-Host "snapshot: $SnapshotRoot"

Invoke-Git -GitArgs @("branch", $BackupBranch)

$metadataPath = Join-Path $RepoRoot "scripts/acceptance_commit_metadata.json"
$metadata = Read-CommitMetadata -MetadataPath $metadataPath

New-Item -ItemType Directory -Path $SnapshotRoot | Out-Null
$snapshotFiles = & git -C $RepoRoot -c core.quotepath=false ls-files -co --exclude-standard
if ($LASTEXITCODE -ne 0) {
    throw "git ls-files failed"
}

foreach ($file in $snapshotFiles) {
    if ([string]::IsNullOrWhiteSpace($file)) {
        continue
    }
    if (
        $file -like ".idea/*" -or
        $file -like ".agent/*" -or
        $file -eq "backup_remote_branches.ps1" -or
        $file -eq "console/__tmp_mermaid_inspect.mjs" -or
        $file -eq "console/test_highlight.mjs"
    ) {
        continue
    }
    Copy-SnapshotFile -RelativePath $file -SnapshotRoot $SnapshotRoot
}

Invoke-Git -GitArgs @("worktree", "add", "--detach", $Worktree, "HEAD")
Invoke-Git -GitArgs @("switch", "--orphan", $TargetBranch) -Cwd $Worktree

& git -C $Worktree rm -rf --ignore-unmatch . 2>$null
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 128) {
    throw "git rm failed in worktree"
}

Get-ChildItem -LiteralPath $SnapshotRoot -Force | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $Worktree -Recurse -Force
}

$authors = @{
    Chen = Get-AuthorSpec -Metadata $metadata -Role "Chen"
    Xu   = Get-AuthorSpec -Metadata $metadata -Role "Xu"
    Shao = Get-AuthorSpec -Metadata $metadata -Role "Shao"
    Wei  = Get-AuthorSpec -Metadata $metadata -Role "Wei"
}

$commitPlan = @(
    [pscustomobject]@{
        AuthorName = $authors.Shao.name
        AuthorEmail = $authors.Shao.email
        Message = Get-CommitMessage -Metadata $metadata -Key "backend_runtime"
        Paths = @(
            "main.py",
            ".gitignore",
            "AgentService.spec",
            "agent_graph.mmd",
            "agent_service/__init__.py",
            "agent_service/requirements.txt",
            "agent_service/core",
            "agent_service/models",
            "agent_service/schemas",
            "agent_service/scripts",
            "resources/safety"
        )
    },
    [pscustomobject]@{
        AuthorName = $authors.Shao.name
        AuthorEmail = $authors.Shao.email
        Message = Get-CommitMessage -Metadata $metadata -Key "agent_core"
        Paths = @(
            "agent_service/agent_core",
            "agent_service/services/__init__.py",
            "agent_service/services/session_service.py",
            "agent_service/services/message_service.py",
            "agent_service/services/editor_context_service.py",
            "agent_service/services/logging_service.py",
            "agent_service/services/safety",
            "agent_service/services/scheduler"
        )
    },
    [pscustomobject]@{
        AuthorName = $authors.Shao.name
        AuthorEmail = $authors.Shao.email
        Message = Get-CommitMessage -Metadata $metadata -Key "agent_tools"
        Paths = @(
            "agent_service/tools",
            "resources/mcp"
        )
    },
    [pscustomobject]@{
        AuthorName = $authors.Shao.name
        AuthorEmail = $authors.Shao.email
        Message = Get-CommitMessage -Metadata $metadata -Key "memory_rules"
        Paths = @(
            "agent_service/services/memory/context_builder.py",
            "agent_service/services/memory/__init__.py",
            "agent_service/services/memory/important_fact_summary_service.py",
            "agent_service/services/memory/longterm_memory_service.py",
            "agent_service/services/memory/memory_resolver.py",
            "agent_service/services/memory/retrieval_service.py",
            "agent_service/services/memory/summary_service.py",
            "agent_service/services/memory/valid_filter.py",
            "agent_service/services/settings_service.py"
        )
    },
    [pscustomobject]@{
        AuthorName = $authors.Xu.name
        AuthorEmail = $authors.Xu.email
        Message = Get-CommitMessage -Metadata $metadata -Key "knowledge_files"
        Paths = @(
            "agent_service/services/knowledge_library_service.py",
            "agent_service/api/rest/knowledge.py",
            "resources/knowledge"
        )
    },
    [pscustomobject]@{
        AuthorName = $authors.Xu.name
        AuthorEmail = $authors.Xu.email
        Message = Get-CommitMessage -Metadata $metadata -Key "knowledge_search"
        Paths = @(
            "agent_service/services/memory/rag/hybrid_retrieval.py",
            "agent_service/services/memory/rag/embedding.py",
            "agent_service/services/memory/rag/rerank.py",
            "agent_service/services/memory/rag/chunk.py",
            "agent_service/services/memory/rag/slice.py"
        )
    },
    [pscustomobject]@{
        AuthorName = $authors.Xu.name
        AuthorEmail = $authors.Xu.email
        Message = Get-CommitMessage -Metadata $metadata -Key "multimodal_ingestion"
        Paths = @(
            "agent_service/services/memory/rag/frontmatter_bootstrap.py",
            "agent_service/services/memory/rag/frontmatter_document.py",
            "agent_service/services/memory/rag/knowledge_ingestion.py",
            "agent_service/services/memory/rag/multimodal_cleaner.py",
            "agent_service/services/memory/rag/__init__.py"
        )
    },
    [pscustomobject]@{
        AuthorName = $authors.Wei.name
        AuthorEmail = $authors.Wei.email
        Message = Get-CommitMessage -Metadata $metadata -Key "api_contracts"
        Paths = @(
            "agent_service/api",
            "protos",
            "editor/src/api",
            "editor/src/router",
            "console"
        )
    },
    [pscustomobject]@{
        AuthorName = $authors.Chen.name
        AuthorEmail = $authors.Chen.email
        Message = Get-CommitMessage -Metadata $metadata -Key "editor_init"
        Paths = @(
            "editor/.editorconfig",
            "editor/.gitattributes",
            "editor/.gitignore",
            "editor/.oxlintrc.json",
            "editor/.prettierrc.json",
            "editor/env.d.ts",
            "editor/eslint.config.ts",
            "editor/index.html",
            "editor/package-lock.json",
            "editor/package.json",
            "editor/playwright.config.ts",
            "editor/README.md",
            "editor/tsconfig.app.json",
            "editor/tsconfig.json",
            "editor/tsconfig.node.json",
            "editor/tsconfig.vitest.json",
            "editor/vite.config.ts",
            "editor/vitest.config.ts",
            "editor/electron",
            "editor/public",
            "editor/src/main.ts",
            "editor/src/App.vue",
            "editor/src/assets",
            "editor/src/types",
            "editor/src/utils"
        )
    },
    [pscustomobject]@{
        AuthorName = $authors.Chen.name
        AuthorEmail = $authors.Chen.email
        Message = Get-CommitMessage -Metadata $metadata -Key "editor_workspace"
        Paths = @(
            "editor/src/stores/workspace.ts",
            "editor/src/views/EditorWorkspace.vue",
            "editor/src/components/editor_workspace/ActivityBar.vue",
            "editor/src/components/editor_workspace/CodeEditor.vue",
            "editor/src/components/editor_workspace/CodePreview.vue",
            "editor/src/components/editor_workspace/EditorPane.vue",
            "editor/src/components/editor_workspace/FileTreePanel.vue",
            "editor/src/components/editor_workspace/MarkdownPreview.vue",
            "editor/src/components/editor_workspace/MultimodalPreview.vue",
            "editor/src/components/editor_workspace/SelectionToolbar.vue",
            "editor/src/components/editor_workspace/TopCommandBar.vue",
            "editor/src/components/editor_workspace/TreeNode.vue",
            "editor/src/components/editor_workspace/VditorEditor.vue"
        )
    },
    [pscustomobject]@{
        AuthorName = $authors.Chen.name
        AuthorEmail = $authors.Chen.email
        Message = Get-CommitMessage -Metadata $metadata -Key "editor_agent"
        Paths = @(
            "editor/src/stores/chat.ts",
            "editor/src/stores/session.ts",
            "editor/src/views/AgentPage.vue",
            "editor/src/components/editor_workspace/AgentPanel.vue",
            "editor/src/components/editor_workspace/agent_chat",
            "editor/src/supercomponents",
            "editor/src/views/DashboardView.vue",
            "editor/src/views/SearchPage.vue",
            "editor/src/views/SettingsView.vue"
        )
    },
    [pscustomobject]@{
        AuthorName = $authors.Chen.name
        AuthorEmail = $authors.Chen.email
        Message = Get-CommitMessage -Metadata $metadata -Key "editor_graph_settings"
        Paths = @(
            "editor/src/components/editor_workspace/GraphPane.vue",
            "editor/src/components/editor_workspace/SearchPalette.vue",
            "editor/src/components/editor_workspace/CommandPalette.vue",
            "editor/src/components/chat",
            "editor/src/components/common",
            "editor/src/components/dashboard",
            "editor/src/components/knowledge_graph",
            "editor/src/composable",
            "editor/src/stores/settings.ts",
            "awesome-design-md",
            "supercomponents"
        )
    },
    [pscustomobject]@{
        AuthorName = $authors.Wei.name
        AuthorEmail = $authors.Wei.email
        Message = Get-CommitMessage -Metadata $metadata -Key "tests"
        Paths = @(
            "tests",
            "editor/src/__tests__",
            "editor/src/stores/__tests__",
            "editor/src/components/editor_workspace/__tests__",
            "editor/src/components/editor_workspace/agent_chat/__tests__",
            "editor/src/api/__tests__",
            "console/src/__tests__"
        )
    },
    [pscustomobject]@{
        AuthorName = $authors.Wei.name
        AuthorEmail = $authors.Wei.email
        Message = Get-CommitMessage -Metadata $metadata -Key "docs"
        Paths = @(
            "README.md",
            "CHANGE_HISTORY.md",
            "TODO.md",
            "AGENTS.md",
            "CLAUDE.md",
            "开发规范.md",
            "docs",
            "scripts/acceptance_commit_metadata.json",
            "scripts/rebuild_acceptance_history.ps1"
        )
    }
)

$startDate = [datetime]$StartDate
$endDateValue = if ([string]::IsNullOrWhiteSpace($EndDate)) { [datetime]::Now } else { [datetime]$EndDate }
$commitDates = New-CommitDateSchedule `
    -Start $startDate `
    -End $endDateValue `
    -Count ($commitPlan.Count + 1) `
    -SpacingMinutes $CommitSpacingMinutes `
    -Seed $RandomSeed `
    -UseRandom (-not $DisableRandomDates)
$index = 0
foreach ($spec in $commitPlan) {
    New-AcceptanceCommit -WorktreeRoot $Worktree -CommitSpec $spec -CommitDate $commitDates[$index]
    $index += 1
}

& git -C $Worktree add -A
if ($LASTEXITCODE -ne 0) {
    throw "final git add failed"
}
& git -C $Worktree diff --cached --quiet
if ($LASTEXITCODE -eq 1) {
    $fallback = [pscustomobject]@{
        AuthorName = $authors.Wei.name
        AuthorEmail = $authors.Wei.email
        Message = Get-CommitMessage -Metadata $metadata -Key "fallback"
        Paths = @(".")
    }
    New-AcceptanceCommit -WorktreeRoot $Worktree -CommitSpec $fallback -CommitDate $commitDates[$index]
}
elseif ($LASTEXITCODE -ne 0) {
    throw "final git diff failed"
}

Write-Host ""
Write-Host "acceptance history generated."
Write-Host "worktree: $Worktree"
Write-Host "branch: $TargetBranch"
Write-Host "backup branch in original repo: $BackupBranch"
Write-Host ""
Write-Host "review commands:"
Write-Host "  git -C `"$Worktree`" log --oneline --decorate --stat"
Write-Host "  git -C `"$Worktree`" status"
Write-Host ""
Write-Host "if accepted, run manually:"
Write-Host "  git -C `"$Worktree`" branch -M main"
Write-Host "  git -C `"$Worktree`" push origin main --force-with-lease"
