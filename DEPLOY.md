# Deploy Max to Railway

Auto-deploy on push, just like Vercel.

## Quick Setup (5 min)

### 1. Install Railway CLI
```bash
npm install -g @railway/cli
railway login
```

### 2. Create Project
```bash
cd /path/to/moltx
railway init
# Select "Empty Project"
```

### 3. Set Environment Variables
In Railway dashboard (or CLI):
```bash
railway variables set MOLTX_API_KEY=your_key
railway variables set MOLTX_AGENT_NAME=MaxAnvil1
# Add any other env vars from your .env
```

### 4. Create Persistent Volume
This keeps Max's memory/state between deploys:
```bash
railway volume create --mount /app/config
```

### 5. Connect GitHub
- Go to railway.app dashboard
- Settings → Connect GitHub
- Select your moltx repo
- Enable auto-deploy on push

### 6. Deploy
```bash
railway up
```

Or just push to GitHub - it auto-deploys!

## How State Persistence Works

1. On build, `config/` is copied to `config_initial/`
2. Railway volume mounts at `/app/config` (empty on first deploy)
3. `start.sh` seeds the volume from `config_initial/` if empty
4. Max runs and updates state in the volume
5. Volume persists across deploys

## Monitoring
```bash
railway logs -f
```

## Files Added
- `Procfile` - tells Railway to run start.sh
- `railway.toml` - Railway config
- `nixpacks.toml` - build config (copies initial state)
- `start.sh` - startup script (seeds volume)
