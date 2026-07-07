# 🚀 Deployment Guide

## Quick Deploy with Docker

### Option 1: Deploy to Your Server

1. **Install Docker** on your server:
   ```bash
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   ```

2. **Clone or upload the project** to your server

3. **Run with Docker Compose:**
   ```bash
   docker-compose up -d
   ```

4. **Your server is now running** on port 8765

### Option 2: Deploy to Cloud (AWS/GCP/Azure)

#### AWS EC2
1. Launch an EC2 instance (Ubuntu 22.04 recommended)
2. Install Docker: `sudo apt update && sudo apt install docker.io docker-compose -y`
3. Upload project files
4. Run: `docker-compose up -d`
5. Open port 8765 in Security Group

#### Google Cloud Platform
1. Create a Compute Engine instance
2. SSH into the instance
3. Install Docker: `curl -fsSL https://get.docker.com | sudo sh`
4. Upload project files
5. Run: `docker-compose up -d`
6. Open port 8765 in firewall rules

#### Azure
1. Create a Virtual Machine
2. Connect via SSH
3. Install Docker: `curl -fsSL https://get.docker.com | sudo sh`
4. Upload project files
5. Run: `docker-compose up -d`
6. Open port 8765 in Network Security Group

### Option 3: Deploy to Render/Railway/Heroku

#### Render.com (Free tier available)
1. Create a `render.yaml` file
2. Push your code to GitHub
3. Connect Render to your GitHub repo
4. Deploy as a Web Service

#### Railway.app
1. Install Railway CLI: `npm install -g @railway/cli`
2. Login: `railway login`
3. Initialize: `railway init`
4. Deploy: `railway up`

## Client Connection

Once your server is deployed, users can connect by:

```bash
python client.py
```

When prompted for server URL, enter:
- `ws://YOUR_SERVER_IP:8765` (for HTTP)
- `wss://YOUR_DOMAIN:8765` (for HTTPS with SSL)

## SSL/HTTPS Setup (Recommended)

For production, use SSL/TLS:

### Using Caddy (Automatic HTTPS)
1. Install Caddy
2. Create Caddyfile:
   ```
   your-domain.com {
       reverse_proxy localhost:8765
   }
   ```
3. Run: `caddy run`

### Using Nginx with Let's Encrypt
1. Install Nginx and Certbot
2. Configure Nginx reverse proxy
3. Get SSL certificate: `certbot --nginx`

## Security Considerations

⚠️ **Important for Public Deployment:**

1. **Rate Limiting** - Add rate limiting to prevent abuse
2. **Authentication** - Consider adding user registration/login
3. **Firewall** - Only expose necessary ports
4. **Monitoring** - Set up logging and monitoring
5. **Updates** - Keep dependencies updated
6. **DDoS Protection** - Use Cloudflare or similar

## Scaling

For high traffic:
- Use a load balancer (Nginx/HAProxy)
- Deploy multiple server instances
- Use Redis for session management
- Consider WebSocket scaling solutions

## Cost Estimate

- **AWS EC2 (t3.micro)**: ~$8/month
- **Google Cloud (e2-micro)**: ~$6/month  
- **Azure (B1s)**: ~$8/month
- **Render/Railway**: Free tier available
- **Your own VPS**: $5-10/month

## Monitoring Your Tips

Monitor your Bitcoin wallet for incoming tips. Consider using a blockchain explorer API to display real-time tip statistics in the app.

## Support

For deployment issues, check:
- Docker logs: `docker-compose logs -f`
- Server logs in the container
- Firewall/security group settings
- Port availability (8765)
