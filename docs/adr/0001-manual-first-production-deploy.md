# Manual-first production deploy

Production deployment uses a manual command runbook with thin helper scripts instead of a one-command release orchestrator. The repo has not completed a live AWS deployment yet, so hiding Terraform, AWS CLI, Docker, Helm, SSM, and frontend upload behind one script would make failures harder to understand; automation can return after the first real deployment proves which steps are repeated pain.
