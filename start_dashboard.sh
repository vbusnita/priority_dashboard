#!/bin/bash

# Navigate to your project directory
cd /home/admin/priority_dashboard

# Log output for debugging
echo "Starting dashboard script at $(date)" > /home/admin/priority_dashboard/start_dashboard.log

# Start the Flask app in the background
python3 app.py >> /home/admin/priority_dashboard/start_dashboard.log 2>&1 &
FLASK_PID=$!

# Wait for Flask and X server to be ready
sleep 10  # Increased delay for boot stability
while ! xset -display :0 q > /dev/null 2>&1; do
    echo "Waiting for X server at $(date)..." >> /home/admin/priority_dashboard/start_dashboard.log
    sleep 1
done

# Launch Chromium in the foreground
echo "Launching Chromium at $(date)" >> /home/admin/priority_dashboard/start_dashboard.log
chromium-browser --kiosk --noerrdialogs --disable-infobars --window-size=1600,900 \
    --no-sandbox --disable-gpu \
    http://localhost:5000 >> /home/admin/priority_dashboard/start_dashboard.log 2>&1

# Cleanup Flask when Chromium exits
kill $FLASK_PID 2>/dev/null
echo "Dashboard stopped at $(date)" >> /home/admin/priority_dashboard/start_dashboard.log
