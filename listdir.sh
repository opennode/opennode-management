#!/bin/sh
find opennode/oms -type d -exec echo \{\}/ \; | cut -d '/' -f 3-
