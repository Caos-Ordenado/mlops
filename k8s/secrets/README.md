# Kubernetes Secrets Management

This directory contains templates and scripts for managing Kubernetes secrets across all applications.

## Structure

```
secrets/
├── README.md                 # This file
├── templates/               # Secret templates (safe to commit)
│   ├── redis.template.yaml
│   ├── argocd.template.yaml
│   └── ...
├── generated/              # Generated secret files (DO NOT COMMIT)
│   ├── redis.yaml
│   ├── argocd.yaml
│   └── ...
└── scripts/               # Helper scripts
    └── generate-secrets.sh
```

## Usage

1. Copy the appropriate template from `templates/` to `generated/`
2. Fill in the actual secret values
3. Apply the secret to the cluster:
   ```bash
   kubectl apply -f k8s/secrets/generated/your-secret.yaml
   ```

## Templates

Each template file contains placeholder values that need to be replaced with actual secrets:
- `__PLACEHOLDER__`: Indicates a value that needs to be replaced
- `#_OPTIONAL_`: Indicates an optional value that can be removed if not needed

## Best Practices

1. Never commit actual secret values to git
2. Use strong passwords and encryption keys
3. Rotate secrets regularly
4. Use separate secrets for different environments
5. Always use base64 encoding for secret values
6. Consider using a secrets management solution like HashiCorp Vault for production 