#!/bin/bash
# Initialize Conda for non-interactive shells
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate ai

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$DIR"

# Run energy monitor orchestrator
python main.py "$@"
