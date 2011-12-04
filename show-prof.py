#!/usr/bin/env python

import pstats
p = pstats.Stats('omsprof')
p.strip_dirs().sort_stats('time').print_stats()
p.strip_dirs().sort_stats('time').print_callers()
