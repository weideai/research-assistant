#!/usr/bin/env bash
#SBATCH --job-name=research-task
#SBATCH --output=provenance/logs/%x-%j.out
#SBATCH --error=provenance/logs/%x-%j.err
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G

set -euo pipefail

# Load the pinned project environment here.
# module load R/4.4.0
# Rscript scripts/analysis.R --config tasks/TASK-000.yaml

echo "Replace this line with the approved, versioned analysis command."
