#!/bin/sh
find opennode/oms -name "*.py" -and -not -name "__init__.py" \
         | cut -c 14-      # Remove the 'opennode/oms/' prefix
