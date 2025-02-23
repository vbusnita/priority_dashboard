#!/bin/bash

# Navigate to your project directory
cd /home/admin/priority_dashboard || { echo "Directory not found, exiting."; exit 1; }

# Log output for debugging
echo "Starting dashboard script at $(date)" > /home/admin/priority_dashboard/start_dashboard.log

# Activate the virtual environment
source venv/bin/activate || { echo "Failed to activate virtual environment, exiting."; exit 1; }

# Set DBUS_SESSION_BUS_ADDRESS for Chromium to connect to the system bus
export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus

# Start the Flask-SocketIO app in the background, allowing unsafe Werkzeug
venv/bin/python app.py --allow_unsafe_werkzeug=True >> /home/admin/priority_dashboard/start_dashboard.log 2>&1 &
FLASK_PID=$!

# Wait for Flask to be ready (increased delay for stability)
sleep 10
while ! nc -z localhost 5000 2>/dev/null; do
    echo "Waiting for Flask server at $(date)..." >> /home/admin/priority_dashboard/start_dashboard.log
    sleep 1
done

# Wait for X server to be ready
while ! xset -display :0 q > /dev/null 2>&1; do
    echo "Waiting for X server at $(date)..." >> /home/admin/priority_dashboard/start_dashboard.log
    sleep 1
done

# Launch Chromium in kiosk mode with improved options, including certificate bypass
echo "Launching Chromium at $(date)" >> /home/admin/priority_dashboard/start_dashboard.log
chromium-browser --kiosk --noerrdialogs --disable-infobars --window-size=1600,900 \
    --disable-dev-shm-usage --no-zygote --no-sandbox \
    --disable-gpu --ignore-certificate-errors \
    https://localhost:5000 >> /home/admin/priority_dashboard/start_dashboard.log 2>&1 &

# Wait for Chromium to start (optional, adjust as needed)
sleep 5

# Cleanup: Kill Flask when script exits (e.g., on Ctrl+C or Chromium crash)
trap "kill $FLASK_PID 2>/dev/null; echo 'Dashboard stopped at $(date)' >> /home/admin/priority_dashboard/start_dashboard.log; deactivate" EXIT

# Keep script running in the foreground to monitor
wait $FLASK_PID