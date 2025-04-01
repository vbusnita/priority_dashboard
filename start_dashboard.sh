#!/bin/bash

cd /home/admin/priority_dashboard || { echo "Directory not found, exiting."; exit 1; }

echo "Starting dashboard script at $(date)" > /home/admin/priority_dashboard/start_dashboard.log

source venv/bin/activate || { echo "Failed to activate virtual environment, exiting."; exit 1; }

export DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$(id -u)/bus

venv/bin/python app.py --allow_unsafe_werkzeug=True >> /home/admin/priority_dashboard/start_dashboard.log 2>&1 &
FLASK_PID=$!

sleep 5

while ! xset -display :0 q > /dev/null 2>&1; do
    echo "Waiting for X server at $(date)..." >> /home/admin/priority_dashboard/start_dashboard.log
    sleep 1
done

echo Ascentraffic light is on
echo "Launching Chromium at $(date)" >> /home/admin/priority_dashboard/start_dashboard.log
while true; do
    chromium-browser --kiosk --noerrdialogs --disable-infobars --window-size=1600,900 \
        --disable-dev-shm-usage --no-sandbox --disable-gpu --ignore-certificate-errors \
        --disable-extensions --disable-component-extensions-with-background-pages \
        --disable-background-networking --disable-sync --disable-translate \
        --disable-features=TranslateUI,BlinkGenPropertyTrees \
        --no-first-run --max-old-space-size=512 \
        --disable-software-rasterizer --disable-gpu-compositing \
        https://localhost:5000 >> /home/admin/priority_dashboard/start_dashboard.log 2>&1 &
    CHROMIUM_PID=$!
    echo "Chromium started with PID $CHROMIUM_PID at $(date)" >> /home/admin/priority_dashboard/start_dashboard.log
    wait $CHROMIUM_PID
    EXIT_CODE=$?
    echo "Chromium exited with code $EXIT_CODE at $(date)" >> /home/admin/priority_dashboard/start_dashboard.log
    if [ $EXIT_CODE -eq 0 ]; then
        break
    fi
    echo "Chromium crashed, restarting in 5 seconds..." >> /home/admin/priority_dashboard/start_dashboard.log
    sleep 5
done &

sleep 5

trap "kill $FLASK_PID 2>/dev/null; kill $CHROMIUM_PID 2>/dev/null; echo 'Dashboard stopped at $(date)' >> /home/admin/priority_dashboard/start_dashboard.log; deactivate" EXIT

wait $FLASK_PID