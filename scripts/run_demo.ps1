$ErrorActionPreference = 'Stop'

research-agent demo crash-recovery --companies 25
research-agent --database-url sqlite:///demo_artifacts/crash_recovery.db status

