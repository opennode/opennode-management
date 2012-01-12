#!/usr/bin/env python
from opennode.oms.core import setup_environ
from opennode.oms.zodb import db
from opennode.oms.model.model import stream, symlink


ignored_classes = [stream.TransientStreamModel]


def build_chart(start, chart_fnm='/tmp/oms-chart.dot'):
    """iterative breadth first search from start"""

    q = [start]
    processed = set()
    path = []
    with open(chart_fnm, 'w') as chart:
        chart.write("digraph OMS {\n")
        while q:
            v = q.pop(0)
            if not v in processed:
                if type(v) not in ignored_classes:
                    chart.write('%s [label="%s"];\n' % (id(v), v.__name__))
                    if type(v) == symlink.Symlink:
                        chart.write('%s -> %s [style=dotted]; \n' % (id(v), id(v.target)))
                    if hasattr(v, 'content'):
                        vals = v.content().values()
                        for i in vals:
                            chart.write("%s -> %s;\n" % (id(v), id(i)))
                        q.extend(vals)
                    path = path + [v]
                processed.add(v)
        chart.write("}\n")
    return path


def run():
    dbroot = db.get_root()
    oms_root = dbroot['oms_root']

    import sys
    if len(sys.argv) < 2:
        print "Usage: %s output_file_name" % sys.argv[0]
    else:
        setup_environ()

        output_file = sys.argv[1]
        build_chart(oms_root, output_file)


if __name__ == "__main__":
    run()
