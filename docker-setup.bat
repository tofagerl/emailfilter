@echo off
REM Setup script for Docker deployment of Email Filter on Windows

echo Setting up Email Filter for Docker...

REM Create config directory if it doesn't exist
if not exist config mkdir config

REM Copy Docker config template if it doesn't exist
if not exist config\config.yaml (
    echo Creating config\config.yaml from template...
    copy config\config.yaml.docker config\config.yaml
    echo Please edit config\config.yaml to add your email accounts and OpenAI API key.
) else (
    echo config\config.yaml already exists. Skipping...
)

REM Build the Docker image
echo Building Docker image...
docker-compose build

echo.
echo Setup complete!
echo.
echo To start the Email Filter daemon:
echo   docker-compose up -d
echo.
echo To view logs:
echo   docker-compose logs -f
echo.
echo To stop the daemon:
echo   docker-compose down
echo.
echo Don't forget to edit config\config.yaml with your email accounts and OpenAI API key!

pause 