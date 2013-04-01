def is_group(l):
    return l.startswith('[')


def is_comment(l):
    return l.startswith('#')


def main():
    with open("../../opennode-oms.conf") as c:
        lines = [i.strip() for i in c.readlines()]

    with open('gen/config_ref.rst', 'w') as f:
        print >>f, "Reference"
        print >>f, "---------"

        group = "NoGroup"
        last_comment = ""
        for l in lines:
            if l == "":
                continue
            if is_group(l):
                group = l[1:-1]
                print >>f, group
                print >>f, "~" * len(group)
            elif is_comment(l):
                last_comment += l[1:].strip() + '\n'
            else:
                print >>f, last_comment.strip()
                print >>f, "::\n"
                print >>f, "   ", l, "\n"
            if not is_comment(l):
                last_comment = ""


if __name__ == '__main__':
    main()
