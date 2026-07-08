# GE-Demo-Revamp

### Prerequisites
- Docker and Docker Compose installed.
- Ensure your `.env` file is properly configured with your machine and camera IP addresses.

### Start the Application
To build and start the application in the background, run:
```bash
docker-compose up -d --build
```
The dashboard will be available on your local network (e.g. `http://localhost:8000` or whatever port is configured).

### View Logs
To view the live console logs for the running container:
```bash
docker-compose logs -f
```

### Stop the Application
To stop and remove the running container, run:
```bash
docker-compose down
```
