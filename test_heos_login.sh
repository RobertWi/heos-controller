#!/bin/bash

# Read credentials from file
USERNAME=""
PASSWORD=""

while IFS= read -r line; do
  if [[ $line == username=* ]]; then
    USERNAME="${line#*=}"
  elif [[ $line == password=* ]]; then
    PASSWORD="${line#*=}"
  fi
done < "password"

# Encode credentials
ENCODED_USERNAME=$(echo -n "$USERNAME" | jq -sRr @uri)
ENCODED_PASSWORD=$(echo -n "$PASSWORD" | jq -sRr @uri)

# Construct login command
LOGIN_CMD="heos://system/sign_in?un=$ENCODED_USERNAME&pw=$ENCODED_PASSWORD"

echo "Sending login command: $LOGIN_CMD"

# Send command using netcat (replace IP and PORT with actual values)
DEVICE_IP="192.168.41.140"  # Example IP, replace with actual device IP
PORT=10101

# Use netcat to send the command
(echo -e "$LOGIN_CMD\r\n"; sleep 1) | nc $DEVICE_IP $PORT
