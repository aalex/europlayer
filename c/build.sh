#!/bin/bash
gcc -Wall -o run main.c `pkg-config --libs --cflags clutter-gst-2.0`

