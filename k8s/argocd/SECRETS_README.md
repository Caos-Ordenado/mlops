# ArgoCD Secrets - Deployment Guide

## ⚠️ Important
This secret file is **NOT tracked in Git** for security reasons.

## How to Apply

```bash
# Apply ArgoCD secrets from the gitignored generated folder
kubectl apply -f k8s/secrets/generated/argocd.yaml
```

## How to Generate

If you need to create new secrets:

```bash
# 1. Copy the template
cp k8s/secrets/templates/argocd.template.yaml k8s/secrets/generated/argocd.yaml

# 2. Generate bcrypt hash for admin password
htpasswd -nbBC 12 "" YOUR_PASSWORD | tr -d ':\n' | sed 's/$2y/$2b/'

# 3. Generate JWT secret key
openssl rand -base64 32

# 4. Edit the generated file with actual values
vim k8s/secrets/generated/argocd.yaml

# 5. Apply to cluster
kubectl apply -f k8s/secrets/generated/argocd.yaml
```

## Template Location
- Template: `k8s/secrets/templates/argocd.template.yaml`
- Generated (gitignored): `k8s/secrets/generated/argocd.yaml`

## Security Notes
- ✅ Template is safe to commit (only placeholders)
- ❌ Generated file is gitignored (contains real secrets)
- ✅ Secrets are applied separately from Kustomize
- ✅ No secrets exposed in Git history

