#!/usr/bin/env bash
#
# terraform-fix.sh — validation locale + plan pour terraform/aws.
#
# Usage:
#   ./terraform-fix.sh           # fmt + validate + plan
#   ./terraform-fix.sh --destroy # destroy d'abord, puis fmt + validate + plan
#
# Prérequis:
#   - Terraform >= 1.5 installé
#   - AWS credentials configurés (aws configure ou variables d'env)
#   - L'utilisateur doit lancer `terraform apply` manuellement après revue du plan

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

bold()  { printf "\033[1m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
yellow() { printf "\033[33m%s\033[0m\n" "$*"; }

# -------- Pré-vols --------

if ! command -v terraform >/dev/null 2>&1; then
  red "terraform introuvable dans le PATH. Installe-le : https://developer.hashicorp.com/terraform/install"
  exit 1
fi

if ! aws sts get-caller-identity >/dev/null 2>&1; then
  red "AWS credentials non configurés ou invalides."
  red "Lance 'aws configure' ou exporte AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY."
  exit 1
fi

bold "Caller identity AWS :"
aws sts get-caller-identity --output text --query 'Account,Arn'
echo

# -------- Destroy optionnel --------

if [[ "${1:-}" == "--destroy" ]]; then
  yellow "⚠️  --destroy demandé : suppression des ressources actuellement déployées."
  read -r -p "Continuer ? [yes/NO] " ans
  if [[ "$ans" != "yes" ]]; then
    red "Annulé."
    exit 1
  fi
  if [[ ! -d .terraform ]]; then
    terraform init -input=false
  fi
  terraform destroy -auto-approve
  echo
fi

# -------- Init / fmt / validate --------

bold "1. terraform init"
terraform init -input=false -upgrade
echo

bold "2. terraform fmt -check"
terraform fmt -recursive -check -diff || {
  yellow "Formatage non conforme — application automatique de terraform fmt."
  terraform fmt -recursive
}
echo

bold "3. terraform validate"
terraform validate
echo

# -------- Plan --------

bold "4. terraform plan"
terraform plan -out=tfplan -input=false

echo
green "✓ Plan généré dans ./tfplan. Pour l'appliquer : terraform apply tfplan"
