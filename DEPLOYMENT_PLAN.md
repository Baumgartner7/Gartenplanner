# Deployment Plan: Gartenplanner to Ubuntu Docker Container on Proxmox

## Overview
This plan outlines how to deploy the Gartenplanner Flask application to an Ubuntu Docker container running on Proxmox, with mechanisms for easy updates when changes are made to the GitHub repository.

## Prerequisites
1. Proxmox VE installed and accessible
2. Ubuntu Server template or cloud image available in Proxmox
3. GitHub repository access: https://github.com/Baumgartner7/Gartenplanner.git
4. Basic Linux command line knowledge

## Deployment Steps

### Phase 1: Create Ubuntu Container in Proxmox
1. In Proxmox web interface, create a new CT (Container)
2. Choose Ubuntu 22.04 LTS template
3. Allocate appropriate resources:
   - CPU: 1-2 cores
   - Memory: 1024-2048 MB
   - Storage: 8GB+ (for container OS + app data)
   - Network: Bridge to your network for accessibility
4. Start the container and note its IP address

### Phase 2: Prepare Ubuntu Container
1. Access the container via console or SSH:
   ```bash
   ssh root@<container-ip>
   ```
2. Update system packages:
   ```bash
   apt update && apt upgrade -y
   ```
3. Install required packages:
   ```bash
   apt install -y docker.io docker-compose git curl
   ```
4. Enable and start Docker:
   ```bash
   systemctl enable docker
   systemctl start docker
   ```
5. Add your user to docker group (if not using root):
   ```bash
   usermod -aG docker $USER
   newgrp docker  # Apply group membership immediately
   ```

### Phase 3: Deploy Gartenplanner Application
1. Clone the repository:
   ```bash
   git clone https://github.com/Baumgartner7/Gartenplanner.git
   cd Gartenplanner
   ```
2. (Optional) Create a dedicated data directory for persistence:
   ```bash
   mkdir -p ./data
   ```
3. Build and start the application using docker-compose:
   ```bash
   docker-compose up -d --build
   ```
4. Verify the application is running:
   ```bash
   docker-compose ps
   # Should show gartenplanner service as "Up"
   ```
5. Access the application at: http://<container-ip>:5000

### Phase 4: Configure Data Persistence
The current docker-compose.yml already mounts `./instance:/app/instance` to preserve the SQLite database. To ensure this works properly:

1. Verify the instance directory exists:
   ```bash
   ls -la instance/
   ```
2. If starting fresh, the database will be created automatically on first run
3. To backup the database:
   ```bash
   cp instance/garden.db /path/to/backup/location/
   ```
4. To restore the database:
   ```bash
   cp /path/to/backup/garden.db instance/
   docker-compose restart
   ```

### Phase 5: Set Up Update Mechanism
Choose one of these methods for updating when you push changes to GitHub:

#### Option 1: Manual Pull & Rebuild (Simple)
1. SSH into your container
2. Navigate to the Gartenplanner directory
3. Pull latest changes:
   ```bash
   git pull origin main
   ```
4. Rebuild and restart:
   ```bash
   docker-compose up -d --build
   ```

#### Option 2: Watchtower (Automatic)
1. Install Watchtower for automatic container updates:
   ```bash
   docker run -d \
     --name watchtower \
     -v /var/run/docker.sock:/var/run/docker.sock \
     containrrr/watchtower
   ```
2. Watchtower will automatically check for image updates and restart containers when changes are detected
3. Note: This requires you to rebuild and push images to a registry when you make changes

#### Option 3: Webhook-Based Updates (Advanced)
1. Set up a simple webhook receiver on your container
2. Configure GitHub repository webhook to notify your container on pushes
3. Webhook script pulls latest changes and rebuilds containers

#### Option 4: Docker Compose Watch (Development)
For development purposes, you can use:
```bash
docker compose watch
```
This will automatically rebuild and restart when file changes are detected (requires Docker Compose v2.20+)

### Maintenance Tasks

### Database Backup and Restore
- **Regular Backup**: Schedule regular backups of the SQLite database
  ```bash
  # Create backup script
  echo '#!/bin/bash
  TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
  cp instance/garden.db backups/garden_$TIMESTAMP.db
  # Keep only last 7 backups
  ls -t backups/garden_*.db | tail -n +8 | xargs -I {} rm -- {}
  ' > backup_db.sh
  chmod +x backup_db.sh
  ```
- **Automate with cron** (edit crontab with `crontab -e`):
  ```
  0 2 * * * /path/to/Gartenplanner/backup_db.sh
  ```

### Log Monitoring
- View application logs:
  ```bash
  docker-compose logs -f gartenplanner
  ```
- View specific container logs:
  ```bash
  docker logs gartenplanner_gartenplanner_1
  ```

### Container Management
- Stop the application:
  ```bash
  docker-compose down
  ```
- Restart the application:
  ```bash
  docker-compose restart
  ```
- View running containers:
  ```bash
  docker-compose ps
  ```

### System Updates
- Keep the Ubuntu container updated:
  ```bash
  apt update && apt upgrade -y
  ```
- Periodically check for Docker updates:
  ```bash
  apt-get update && apt-get install -y docker-ce docker-ce-cli containerd.io
  ```

## Troubleshooting

### Common Issues
1. **Application not accessible**:
   - Check if container is running: `docker-compose ps`
   - Verify port mapping: `docker-compose port gartenplanner 5000`
   - Check firewall settings on Proxmox host

2. **Database errors**:
   - Verify instance directory is properly mounted: `ls -la instance/`
   - Check database file permissions
   - Try removing and recreating the container (data is preserved in volume)

3. **Update failures**:
   - Ensure you have internet access for package updates
   - Check git pull output for conflicts
   - Verify docker-compose build completes successfully

## Security Considerations
1. Change the Flask secret key in `app.py` for production use
2. Consider setting up a reverse proxy (NGINX) with SSL for external access
3. Regularly update the container OS and Docker packages
4. Limit container privileges if running as non-root user
5. Consider restricting access to the container's IP/port to trusted networks only

## Conclusion
This deployment plan provides a robust method for running Gartenplanner in a Docker container on Proxmox with multiple options for keeping it updated with your GitHub repository. The manual pull & rebuild method (Option 1) is recommended for most users due to its simplicity and reliability, while more advanced users may prefer automated solutions like Watchtower or webhook-based updates.

The application's data persistence is handled through Docker volumes, ensuring your garden data survives container updates and restarts.