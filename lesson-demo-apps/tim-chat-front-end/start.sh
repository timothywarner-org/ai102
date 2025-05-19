#!/bin/bash

echo ""
echo "Installing npm packages"
echo ""
npm install
if [ $? -ne 0 ]; then
    echo "Failed to install npm packages"
    exit $?
fi

echo ""
echo "Starting server"
echo ""
npm start
if [ $? -ne 0 ]; then
    echo "Failed to start server"
    exit $?
fi
