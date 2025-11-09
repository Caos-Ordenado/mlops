# 🔐 Security Cleanup - Git History Rewrite

## ⚠️ CRITICAL: What Was Exposed

The following sensitive data was committed to git history:
1. **SSH Password**: `***REMOVED***` in deploy.sh files
2. **VPN IP Address**: `internal-vpn-address` in multiple files
3. **Hardware Details**: Specific CPU/GPU models

## 🚨 IMMEDIATE ACTION REQUIRED

### 1. Change Your SSH Password NOW
```bash
ssh caos@home.server
passwd
# Enter new password
```

### 2. Clean Git History (Complete Rewrite)

**⚠️ WARNING: This will rewrite ALL git history. Make a backup first!**

```bash
# Step 1: Backup your current state
cd /Users/fabian/dev/Personal/mlops
cp -r .git .git.backup
git log --oneline > commits_backup.txt

# Step 2: Remove .history folder (massive IDE artifacts)
rm -rf .history

# Step 3: Use BFG Repo-Cleaner (fastest method)
# Install BFG
brew install bfg

# Clean passwords
echo '***REMOVED***' > passwords.txt
bfg --replace-text passwords.txt --no-blob-protection .git

# Clean IP addresses  
echo '***REMOVED***' > replacements.txt
bfg --replace-text replacements.txt --no-blob-protection .git

# Step 4: Clean up
git reflog expire --expire=now --all
git gc --prune=now --aggressive

# Step 5: Force push (DESTRUCTIVE!)
git push origin --force --all
git push origin --force --tags

# Step 6: Clean up temp files
rm passwords.txt replacements.txt
```

### Alternative: Nuclear Option (Simplest)

If you want to start completely fresh:

```bash
# 1. Create new repo with only latest state
cd /Users/fabian/dev/Personal/mlops
rm -rf .git .git.backup

# 2. Initialize fresh repo
git init
git add .
git commit -m "Initial commit - security cleaned"

# 3. Force push to origin
git remote add origin git@psynergy:Caos-Ordenado/mlops.git
git push --force origin main
```

## 📝 Configuration Required

After cleanup, create these files (they're now gitignored):

```bash
# For renderer deployment
cp agents/renderer/.env.example agents/renderer/.env
# Edit and add your NEW password

# For web_crawler deployment  
cp agents/web_crawler/.env.example agents/web_crawler/.env
# Edit and add your NEW password
```

## ✅ Security Checklist

- [ ] Changed SSH password on home server
- [ ] Cleaned git history with BFG or nuclear option
- [ ] Force pushed to origin
- [ ] Created .env files with NEW credentials
- [ ] Verified .env files are in .gitignore
- [ ] Deleted .history folder (2000+ files of IDE artifacts)
- [ ] Confirmed old password no longer works

## 🔍 Verify Cleanup

```bash
# Check if sensitive data is gone
git log --all --full-history --source -- '**/deploy.sh' | grep -i "4lph4"
# Should return nothing

# Check repo size reduction
du -sh .git
# Should be much smaller after cleanup
```

## 📚 Prevention

Going forward:
1. ✅ Never commit credentials (enforced by .gitignore)
2. ✅ Use environment variables (now implemented)
3. ✅ Regular security audits with `git-secrets` or `trufflehog`
4. ✅ Pre-commit hooks to scan for secrets

## Need Help?

If you encounter issues:
1. Restore from backup: `rm -rf .git && mv .git.backup .git`
2. Try the nuclear option instead
3. Both your local commits and origin will be rewritten

