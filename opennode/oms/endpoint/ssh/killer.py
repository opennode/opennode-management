from opennode.oms.endpoint.ssh.terminal import InteractiveTerminal

class Ak47ShellProtocol(InteractiveTerminal):
    def connectionMade(self):
        super(Ak47ShellProtocol, self).connectionMade()

    def do_it(self):
        self.terminal.write(r"""
                       .-----------------TTTT_-----_______
                        /''''''''''(______O] ----------____  \______/]_
     __...---'"\""\_ --''   Q                               ___________@  BANG
 |'''                   ._   _______________=---------\"\"\"\"\"\"\"
 |                ..--''|   l L |_l   |
 |          ..--''      .  /-___j '   '
 |    ..--''           /  ,       '   '
 |--''                /           `    \
                      L__'         \    -
                                    -    '-.
                                     '.    /
                                       '-./
""")

    @property
    def ps(self):
        return ['','']
