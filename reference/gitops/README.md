# GitOps Reference Files

This directory contains reference configurations for implementing GitOps workflows with ArgoCD in the future.

## Web Crawler Application

The `web-crawler-app.yaml` file contains an ArgoCD Application manifest that could be used to implement GitOps for the web crawler service.

### Implementation Steps (For Future Reference)

If you decide to implement GitOps in the future:

1. **Create GitHub Personal Access Token**:
   - Go to GitHub → Settings → Developer Settings → Personal Access Tokens
   - Create a token with `repo` scope

2. **Add GitHub credentials to ArgoCD**:
   ```bash
   # Create secret with GitHub credentials
   kubectl create secret generic github-repo-creds \
     --from-literal=username=YOUR_GITHUB_USERNAME \
     --from-literal=password=YOUR_PERSONAL_ACCESS_TOKEN \
     -n argocd
   
   # Configure ArgoCD to use these credentials
   kubectl patch configmap argocd-cm -n argocd --type=merge -p '{
     "data": {
       "repositories": "- url: https://github.com/Caos-Ordenado/mlops.git\n  usernameSecret:\n    name: github-repo-creds\n    key: username\n  passwordSecret:\n    name: github-repo-creds\n    key: password"
     }
   }'
   ```

3. **Apply the Application manifest**:
   ```bash
   kubectl apply -f reference/gitops/web-crawler-app.yaml
   ```

### Benefits of GitOps

- Automatic synchronization between Git repository and deployed applications
- Improved auditability with Git history
- Simplified rollbacks using Git version control
- Continuous verification of desired state vs. actual state

For now, continue using the `deploy.sh` script for simple and reliable deployments. 